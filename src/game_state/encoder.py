"""
FeatureEncoder — canonical game state → feature vector.

The encoder is stateless: ``encode(state)`` is pure and deterministic.
The same GameState always produces the same feature vector regardless of
object identity or creation order.

Encoding formats
----------------
- ``encode(state)``         → EncodedFeatures (all formats at once)
- ``encode_flat(state)``    → tuple[float, ...]
- ``encode_groups(state)``  → dict[FeatureGroup, tuple[float, ...]]
- ``encode_sparse(state)``  → dict[int, float]  (non-zero only)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.game_state.actions import ActionType
from src.game_state.features import (
    EMBEDDING_DIM,
    GROUP_OFFSETS,
    GROUP_SIZES,
    HISTORY_LENGTH,
    MAX_BENCH_SIZE,
    MAX_DECK_SIZE,
    MAX_PRIZES,
    MAX_TURN,
    NUM_ACTION_TYPES,
    NUM_ENERGY_TYPES,
    NUM_STAGE_SLOTS,
    POKEMON_FEAT_SIZE,
    FeatureGroup,
)
from src.game_state.models import CardInstance
from src.game_state.zones import (
    CardCategory,
    EnergyTypeCode,
    PokemonStage,
    SpecialCondition,
)

if TYPE_CHECKING:
    from src.game_state.player import PlayerState
    from src.game_state.state import GameState


# -------------------------------------------------------------------------
# Result container
# -------------------------------------------------------------------------

@dataclass(frozen=True)
class EncodedFeatures:
    """
    All encodings of a single GameState, produced by FeatureEncoder.

    Attributes
    ----------
    flat : tuple[float, ...]
        Dense flat feature vector of length TOTAL_FEATURE_SIZE.
    groups : dict[str, tuple[float, ...]]
        Feature vector split by named group.
    total_size : int
        Should equal TOTAL_FEATURE_SIZE (provided for sanity checks).
    perspective : int
        Which player's perspective was used (0 or 1).
    """
    flat: tuple[float, ...]
    groups: dict[str, tuple[float, ...]]
    total_size: int
    perspective: int = 0

    def group(self, name: FeatureGroup) -> tuple[float, ...]:
        return self.groups[name.value]

    def sparse(self) -> dict[int, float]:
        return {i: v for i, v in enumerate(self.flat) if v != 0.0}

    def as_list(self) -> list[float]:
        return list(self.flat)

    def slice(self, group: FeatureGroup) -> tuple[float, ...]:
        start, end = GROUP_OFFSETS[group]
        return self.flat[start:end]


# -------------------------------------------------------------------------
# Encoder
# -------------------------------------------------------------------------

_ENERGY_ORDER = EnergyTypeCode.ordered()
_ACTION_ORDER = ActionType.ordered()
_COND_ORDER = (
    SpecialCondition.BURNED,
    SpecialCondition.POISONED,
    SpecialCondition.PARALYZED,
    SpecialCondition.CONFUSED,
    SpecialCondition.ASLEEP,
)


class FeatureEncoder:
    """
    Stateless canonical encoder from GameState to feature vectors.

    Usage::

        encoder = FeatureEncoder()
        features = encoder.encode(state)
        flat_vec = features.flat                  # tuple[float, ...]
        active_feats = features.group(FeatureGroup.ACTIVE_SELF)
    """

    def encode(self, state: GameState, perspective: int = -1) -> EncodedFeatures:
        """
        Encode state from a given player's perspective.

        perspective=-1 uses state.current_player automatically.
        """
        pov = state.current_player if perspective == -1 else perspective
        groups: dict[str, tuple[float, ...]] = {}

        self_player = state.players[pov]
        opp_player = state.players[1 - pov]

        # --- Current player blocks ---
        groups[FeatureGroup.ACTIVE_SELF.value] = self._encode_active(
            state, self_player
        )
        groups[FeatureGroup.BENCH_SELF.value] = self._encode_bench(
            state, self_player
        )
        groups[FeatureGroup.HAND_SELF.value] = self._encode_hand_self(
            state, self_player
        )
        groups[FeatureGroup.DECK_SELF.value] = self._encode_deck(self_player)
        groups[FeatureGroup.PRIZES_SELF.value] = self._encode_prizes(self_player)
        groups[FeatureGroup.DISCARD_SELF.value] = self._encode_discard(self_player)
        groups[FeatureGroup.LOST_ZONE_SELF.value] = self._encode_lost_zone(self_player)

        # --- Opponent blocks ---
        groups[FeatureGroup.ACTIVE_OPP.value] = self._encode_active(
            state, opp_player
        )
        groups[FeatureGroup.BENCH_OPP.value] = self._encode_bench(
            state, opp_player
        )
        groups[FeatureGroup.HAND_OPP.value] = (
            min(1.0, opp_player.hand_count / 20.0),
        )
        groups[FeatureGroup.DECK_OPP.value] = self._encode_deck(opp_player)
        groups[FeatureGroup.PRIZES_OPP.value] = self._encode_prizes(opp_player)
        groups[FeatureGroup.DISCARD_OPP.value] = self._encode_discard(opp_player)
        groups[FeatureGroup.LOST_ZONE_OPP.value] = self._encode_lost_zone(opp_player)

        # --- Shared ---
        groups[FeatureGroup.STADIUM.value] = (
            1.0 if state.stadium_instance_id is not None else 0.0,
        )
        groups[FeatureGroup.TURN.value] = self._encode_turn(state, pov)
        groups[FeatureGroup.HISTORY.value] = self._encode_history(state)
        groups[FeatureGroup.EMBEDDINGS.value] = self._encode_embeddings()

        # Validate sizes
        for fg in FeatureGroup.ordered():
            vec = groups[fg.value]
            expected = GROUP_SIZES[fg]
            assert len(vec) == expected, (
                f"Group {fg.value}: expected {expected}, got {len(vec)}"
            )

        # Build flat vector
        flat: list[float] = []
        for fg in FeatureGroup.ordered():
            flat.extend(groups[fg.value])

        return EncodedFeatures(
            flat=tuple(flat),
            groups=groups,
            total_size=len(flat),
            perspective=pov,
        )

    def encode_flat(self, state: GameState, perspective: int = -1) -> tuple[float, ...]:
        return self.encode(state, perspective).flat

    def encode_groups(
        self, state: GameState, perspective: int = -1
    ) -> dict[str, tuple[float, ...]]:
        return self.encode(state, perspective).groups

    def encode_sparse(
        self, state: GameState, perspective: int = -1
    ) -> dict[int, float]:
        return self.encode(state, perspective).sparse()

    # ------------------------------------------------------------------ #
    # Pokémon slot encoding (28 features)
    # ------------------------------------------------------------------ #

    def _encode_pokemon_slot(
        self,
        state: GameState,
        instance_id: str | None,
    ) -> tuple[float, ...]:
        feats: list[float] = []

        if instance_id is None:
            return tuple([0.0] * POKEMON_FEAT_SIZE)

        inst = state.card_instances.get(instance_id)
        if inst is None:
            return tuple([0.0] * POKEMON_FEAT_SIZE)

        # [0] present
        feats.append(1.0)

        # [1] hp_ratio
        feats.append(inst.hp_ratio)

        # [2] damage_ratio
        if inst.max_hp > 0:
            feats.append(min(1.0, inst.damage_taken / inst.max_hp))
        else:
            feats.append(0.0)

        # [3..13] attached energy counts by type (normalized to [0,1] with max=5)
        energy_counts = [0.0] * NUM_ENERGY_TYPES
        for eid in inst.attached_energy_ids:
            e_inst = state.card_instances.get(eid)
            if e_inst is not None:
                etype = self._infer_energy_type(e_inst)
                idx = list(_ENERGY_ORDER).index(etype)
                energy_counts[idx] += 1.0
        feats.extend(min(1.0, c / 5.0) for c in energy_counts)

        # [14..18] special conditions
        for cond in _COND_ORDER:
            feats.append(1.0 if cond in inst.special_conditions else 0.0)

        # [19] retreat cost (0 if not a Pokémon)
        feats.append(0.0)  # placeholder — simulator fills retreat cost

        # [20] has_attacked
        feats.append(1.0 if inst.has_attacked else 0.0)

        # [21] has_retreated
        feats.append(1.0 if inst.has_retreated else 0.0)

        # [22] prize_value
        feats.append(inst.prize_value / 2.0)

        # [23] tool attached
        feats.append(1.0 if inst.attached_tool_id is not None else 0.0)

        # [24..27] stage one-hot
        stage_idx = PokemonStage.stage_index(inst.stage)
        stage_vec = [0.0] * NUM_STAGE_SLOTS
        stage_vec[stage_idx] = 1.0
        feats.extend(stage_vec)

        assert len(feats) == POKEMON_FEAT_SIZE
        return tuple(feats)

    def _encode_active(
        self, state: GameState, player: PlayerState
    ) -> tuple[float, ...]:
        return self._encode_pokemon_slot(state, player.active)

    def _encode_bench(
        self, state: GameState, player: PlayerState
    ) -> tuple[float, ...]:
        feats: list[float] = []
        bench = list(player.bench)[:MAX_BENCH_SIZE]
        for i in range(MAX_BENCH_SIZE):
            iid = bench[i] if i < len(bench) else None
            feats.extend(self._encode_pokemon_slot(state, iid))
        return tuple(feats)

    # ------------------------------------------------------------------ #
    # Hand / deck / zones
    # ------------------------------------------------------------------ #

    def _encode_hand_self(
        self, state: GameState, player: PlayerState
    ) -> tuple[float, ...]:
        count = 0
        energy = item = supporter = pokemon = stadium = tool = 0

        for iid in player.hand:
            inst = state.card_instances.get(iid)
            if inst is None:
                continue
            count += 1
            cat = inst.category
            if cat == CardCategory.POKEMON:
                pokemon += 1
            elif cat == CardCategory.ENERGY_BASIC or cat == CardCategory.ENERGY_SPECIAL:
                energy += 1
            elif cat == CardCategory.TRAINER_ITEM:
                item += 1
            elif cat == CardCategory.TRAINER_SUPPORTER:
                supporter += 1
            elif cat == CardCategory.TRAINER_STADIUM:
                stadium += 1
            elif cat == CardCategory.TRAINER_TOOL:
                tool += 1

        total = max(player.hand_count, 1)
        return (
            min(1.0, player.hand_count / 20.0),  # [0] total count normalized
            energy / total,                        # [1] energy fraction
            pokemon / total,                       # [2] pokemon fraction
            item / total,                          # [3] item fraction
            supporter / total,                     # [4] supporter fraction
            stadium / total,                       # [5] stadium fraction
            tool / total,                          # [6] tool fraction
        )

    def _encode_deck(self, player: PlayerState) -> tuple[float, ...]:
        ratio = player.deck_size / MAX_DECK_SIZE
        return (
            min(1.0, player.deck_size / MAX_DECK_SIZE),
            min(1.0, ratio),
        )

    def _encode_prizes(self, player: PlayerState) -> tuple[float, ...]:
        return (
            player.prizes_remaining / MAX_PRIZES,
            min(1.0, player.prizes_remaining / MAX_PRIZES),
        )

    def _encode_discard(self, player: PlayerState) -> tuple[float, ...]:
        cnt = player.discard_count
        return (
            min(1.0, cnt / MAX_DECK_SIZE),
            min(1.0, cnt / MAX_DECK_SIZE),
        )

    def _encode_lost_zone(self, player: PlayerState) -> tuple[float, ...]:
        return (min(1.0, player.lost_zone_count / 10.0),)

    # ------------------------------------------------------------------ #
    # Turn / history / embeddings
    # ------------------------------------------------------------------ #

    def _encode_turn(self, state: GameState, pov: int) -> tuple[float, ...]:
        self_player = state.players[pov]
        return (
            min(1.0, state.turn_number / MAX_TURN),
            float(state.current_player == pov),
            1.0 if self_player.supporter_played_this_turn else 0.0,
            1.0 if self_player.energy_attached_this_turn else 0.0,
        )

    def _encode_history(self, state: GameState) -> tuple[float, ...]:
        """Last HISTORY_LENGTH actions, each encoded as action_type one-hot + player bit."""
        recent = state.action_history[-HISTORY_LENGTH:]
        n = len(recent)
        feats: list[float] = []
        for i in range(HISTORY_LENGTH):
            if i < n:
                action = recent[i]
                # action_type one-hot
                one_hot = [0.0] * NUM_ACTION_TYPES
                try:
                    idx = list(_ACTION_ORDER).index(action.action_type)
                    one_hot[idx] = 1.0
                except ValueError:
                    pass
                feats.extend(one_hot)
                feats.append(float(action.player))
            else:
                feats.extend([0.0] * (NUM_ACTION_TYPES + 1))
        return tuple(feats)

    def _encode_embeddings(self) -> tuple[float, ...]:
        """Reserved placeholder for future learned card embeddings."""
        return tuple([0.0] * EMBEDDING_DIM)

    # ------------------------------------------------------------------ #
    # Utilities
    # ------------------------------------------------------------------ #

    @staticmethod
    def _infer_energy_type(inst: CardInstance) -> EnergyTypeCode:
        """Heuristic energy type inference from card name."""
        name_lower = inst.card_name.lower()
        name_map = {
            "fire": EnergyTypeCode.FIRE,
            "water": EnergyTypeCode.WATER,
            "grass": EnergyTypeCode.GRASS,
            "lightning": EnergyTypeCode.LIGHTNING,
            "electric": EnergyTypeCode.LIGHTNING,
            "psychic": EnergyTypeCode.PSYCHIC,
            "fighting": EnergyTypeCode.FIGHTING,
            "darkness": EnergyTypeCode.DARKNESS,
            "dark": EnergyTypeCode.DARKNESS,
            "metal": EnergyTypeCode.METAL,
            "steel": EnergyTypeCode.METAL,
            "dragon": EnergyTypeCode.DRAGON,
            "fairy": EnergyTypeCode.FAIRY,
        }
        for keyword, etype in name_map.items():
            if keyword in name_lower:
                return etype
        return EnergyTypeCode.COLORLESS


# Module-level singleton for convenience
DEFAULT_ENCODER = FeatureEncoder()


def encode(state: GameState, perspective: int = -1) -> EncodedFeatures:
    """Convenience wrapper using the default encoder."""
    return DEFAULT_ENCODER.encode(state, perspective)


def encode_flat(state: GameState, perspective: int = -1) -> tuple[float, ...]:
    return DEFAULT_ENCODER.encode_flat(state, perspective)
