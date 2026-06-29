"""
PlayerState — immutable snapshot of one player's board position.

All mutable lists are stored as tuples. Card references are instance_ids
resolved against GameState.card_instances.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class PlayerState(BaseModel):
    """
    Complete snapshot of a single player's game state.

    Fields that reference cards use ``instance_id`` strings resolved
    against the parent ``GameState.card_instances`` mapping.

    For the opponent's perspective some information is hidden (hand cards,
    deck order, face-down prizes); those fields are empty while the
    corresponding ``*_count`` fields carry the public information.
    """
    model_config = ConfigDict(frozen=True)

    player_id: int                          # 0 or 1

    # --- Board zones (instance_ids) ---
    active: str | None = None            # active Pokémon instance_id
    bench: tuple[str, ...] = ()             # up to 5 instance_ids
    hand: tuple[str, ...] = ()              # known hand instance_ids
    hand_count: int = 0                     # total hand size (includes hidden)
    deck_size: int = 60                     # remaining deck cards
    deck_order: tuple[str, ...] = ()        # known order (hidden for opponent)
    discard: tuple[str, ...] = ()           # instance_ids in discard pile
    lost_zone: tuple[str, ...] = ()         # instance_ids in lost zone
    prizes: tuple[str, ...] = ()            # instance_ids; "" = face-down (hidden)
    prizes_remaining: int = 6              # public prize count

    # --- Turn-level flags ---
    supporter_played_this_turn: bool = False
    energy_attached_this_turn: bool = False
    stadium_played_this_turn: bool = False

    # --- Computed counts (denormalized for fast access) ---
    bench_count: int = 0
    discard_count: int = 0
    lost_zone_count: int = 0

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    @property
    def all_pokemon_ids(self) -> tuple[str, ...]:
        ids: list[str] = []
        if self.active:
            ids.append(self.active)
        ids.extend(self.bench)
        return tuple(ids)

    @property
    def has_active(self) -> bool:
        return self.active is not None

    @property
    def bench_slots_free(self) -> int:
        return max(0, 5 - len(self.bench))

    def with_active(self, instance_id: str | None) -> PlayerState:
        return self.model_copy(update={"active": instance_id})

    def with_bench_added(self, instance_id: str) -> PlayerState:
        new_bench = self.bench + (instance_id,)
        return self.model_copy(update={
            "bench": new_bench,
            "bench_count": len(new_bench),
        })

    def without_bench(self, instance_id: str) -> PlayerState:
        new_bench = tuple(iid for iid in self.bench if iid != instance_id)
        return self.model_copy(update={
            "bench": new_bench,
            "bench_count": len(new_bench),
        })

    def with_card_drawn(self, instance_id: str) -> PlayerState:
        new_hand = self.hand + (instance_id,)
        return self.model_copy(update={
            "hand": new_hand,
            "hand_count": self.hand_count + 1,
            "deck_size": max(0, self.deck_size - 1),
        })

    def with_card_discarded(self, instance_id: str) -> PlayerState:
        new_hand = tuple(iid for iid in self.hand if iid != instance_id)
        new_discard = self.discard + (instance_id,)
        return self.model_copy(update={
            "hand": new_hand,
            "hand_count": max(0, self.hand_count - 1),
            "discard": new_discard,
            "discard_count": self.discard_count + 1,
        })

    def with_prize_taken(self, instance_id: str) -> PlayerState:
        new_prizes = tuple(p for p in self.prizes if p != instance_id)
        remaining = max(0, self.prizes_remaining - 1)
        new_hand = self.hand + (instance_id,)
        return self.model_copy(update={
            "prizes": new_prizes,
            "prizes_remaining": remaining,
            "hand": new_hand,
            "hand_count": self.hand_count + 1,
        })

    def reset_turn_flags(self) -> PlayerState:
        return self.model_copy(update={
            "supporter_played_this_turn": False,
            "energy_attached_this_turn": False,
            "stadium_played_this_turn": False,
        })
