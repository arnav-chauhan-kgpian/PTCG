"""
ActionMask — structured representation of what actions are available.

This module represents the *shape* of legal actions without implementing
any game rules.  A future simulator or rule engine populates the mask;
downstream policy networks consume it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.game_state.state import GameState


# -------------------------------------------------------------------------
# Mask constants (index positions in the flat mask vector)
# -------------------------------------------------------------------------

MASK_CAN_ATTACK = 0
MASK_CAN_RETREAT = 1
MASK_CAN_EVOLVE = 2
MASK_CAN_ATTACH_ENERGY = 3
MASK_CAN_PLAY_SUPPORTER = 4
MASK_CAN_USE_ABILITY = 5
MASK_CAN_PLAY_ITEM = 6
MASK_CAN_END_TURN = 7
MASK_CAN_PLAY_STADIUM = 8
MASK_CAN_PLAY_POKEMON = 9

NUM_GLOBAL_MASK_BITS = 10

# Per-slot masks follow global bits
MAX_ATTACKS = 4          # maximum attacks a Pokémon can have
MAX_BENCH = 5            # bench slots
NUM_ATTACK_MASK_BITS = MAX_ATTACKS              # one bit per attack slot
NUM_BENCH_EVOLVE_BITS = MAX_BENCH               # one bit per bench slot
NUM_BENCH_RETREAT_BITS = MAX_BENCH              # one bit per bench retreat target

TOTAL_MASK_SIZE = NUM_GLOBAL_MASK_BITS + NUM_ATTACK_MASK_BITS + NUM_BENCH_EVOLVE_BITS + NUM_BENCH_RETREAT_BITS
# = 10 + 4 + 5 + 5 = 24


@dataclass(frozen=True)
class ActionMask:
    """
    Binary mask of available actions from the current player's perspective.

    All fields default to False (no actions available).  A simulator or
    rule engine sets the appropriate fields to True.

    The ``as_vector`` property serializes the mask to a fixed-length
    binary float vector for use as a neural network input.
    """

    # --- Global action flags ---
    can_attack: bool = False
    can_retreat: bool = False
    can_evolve: bool = False
    can_attach_energy: bool = False
    can_play_supporter: bool = False
    can_use_ability: bool = False
    can_play_item: bool = False
    can_end_turn: bool = False
    can_play_stadium: bool = False
    can_play_pokemon: bool = False

    # --- Per-slot masks ---
    attack_mask: tuple[bool, ...] = (False, False, False, False)  # per attack slot
    bench_evolve_mask: tuple[bool, ...] = (False,) * 5            # per bench slot
    bench_retreat_mask: tuple[bool, ...] = (False,) * 5           # retreat targets

    # --- Metadata ---
    reason: str | None = None   # why all actions are blocked (if any)

    # ------------------------------------------------------------------ #
    # Properties
    # ------------------------------------------------------------------ #

    @property
    def has_any_action(self) -> bool:
        return any([
            self.can_attack, self.can_retreat, self.can_evolve,
            self.can_attach_energy, self.can_play_supporter,
            self.can_use_ability, self.can_play_item, self.can_end_turn,
            self.can_play_stadium, self.can_play_pokemon,
        ])

    @property
    def as_vector(self) -> tuple[float, ...]:
        """
        Fixed-length binary float vector representation.

        Layout (TOTAL_MASK_SIZE = 24):
        [0]  can_attack
        [1]  can_retreat
        [2]  can_evolve
        [3]  can_attach_energy
        [4]  can_play_supporter
        [5]  can_use_ability
        [6]  can_play_item
        [7]  can_end_turn
        [8]  can_play_stadium
        [9]  can_play_pokemon
        [10..13] attack_mask (per attack slot)
        [14..18] bench_evolve_mask
        [19..23] bench_retreat_mask
        """
        vec: list[float] = [
            float(self.can_attack),
            float(self.can_retreat),
            float(self.can_evolve),
            float(self.can_attach_energy),
            float(self.can_play_supporter),
            float(self.can_use_ability),
            float(self.can_play_item),
            float(self.can_end_turn),
            float(self.can_play_stadium),
            float(self.can_play_pokemon),
        ]
        # Pad/truncate attack mask to MAX_ATTACKS
        atk = list(self.attack_mask)[:MAX_ATTACKS]
        atk += [False] * (MAX_ATTACKS - len(atk))
        vec.extend(float(b) for b in atk)

        # Pad/truncate bench masks to MAX_BENCH
        ev = list(self.bench_evolve_mask)[:MAX_BENCH]
        ev += [False] * (MAX_BENCH - len(ev))
        vec.extend(float(b) for b in ev)

        rt = list(self.bench_retreat_mask)[:MAX_BENCH]
        rt += [False] * (MAX_BENCH - len(rt))
        vec.extend(float(b) for b in rt)

        return tuple(vec)

    @property
    def legal_attack_indices(self) -> tuple[int, ...]:
        return tuple(i for i, ok in enumerate(self.attack_mask) if ok)

    @property
    def legal_evolve_slots(self) -> tuple[int, ...]:
        return tuple(i for i, ok in enumerate(self.bench_evolve_mask) if ok)

    # ------------------------------------------------------------------ #
    # Factories
    # ------------------------------------------------------------------ #

    @classmethod
    def all_blocked(cls, reason: str = "no actions") -> ActionMask:
        return cls(can_end_turn=True, reason=reason)

    @classmethod
    def end_turn_only(cls) -> ActionMask:
        return cls(can_end_turn=True)

    @classmethod
    def from_vector(cls, vec: tuple[float, ...]) -> ActionMask:
        """Reconstruct an ActionMask from its as_vector representation."""
        def b(idx: int) -> bool:
            return vec[idx] > 0.5 if idx < len(vec) else False

        attack = tuple(b(10 + i) for i in range(MAX_ATTACKS))
        evolve = tuple(b(14 + i) for i in range(MAX_BENCH))
        retreat = tuple(b(19 + i) for i in range(MAX_BENCH))

        return cls(
            can_attack=b(0), can_retreat=b(1), can_evolve=b(2),
            can_attach_energy=b(3), can_play_supporter=b(4),
            can_use_ability=b(5), can_play_item=b(6), can_end_turn=b(7),
            can_play_stadium=b(8), can_play_pokemon=b(9),
            attack_mask=attack,
            bench_evolve_mask=evolve,
            bench_retreat_mask=retreat,
        )

    @classmethod
    def placeholder_for_state(cls, state: GameState) -> ActionMask:
        """
        Generate a placeholder mask based purely on public game state.

        This is NOT a rule-based implementation — it simply enables any
        action that could plausibly be legal based on surface-level state.
        A proper simulator should override this with rule-validated masks.
        """
        p = state.players[state.current_player]
        has_active = p.active is not None
        has_bench = len(p.bench) > 0
        has_hand = p.hand_count > 0

        can_attack = has_active
        can_retreat = has_active and has_bench
        can_end_turn = True
        can_play_pokemon = has_hand and len(p.bench) < 5
        can_attach_energy = has_hand and has_active
        can_play_supporter = has_hand and not p.supporter_played_this_turn
        can_play_item = has_hand
        can_use_ability = has_active or has_bench
        can_evolve = has_active or has_bench
        can_play_stadium = has_hand

        bench_evolve = tuple(i < len(p.bench) for i in range(5))
        bench_retreat = tuple(i < len(p.bench) for i in range(5))
        attack_slots = (can_attack, can_attack, False, False)

        return cls(
            can_attack=can_attack,
            can_retreat=can_retreat,
            can_evolve=can_evolve,
            can_attach_energy=can_attach_energy,
            can_play_supporter=can_play_supporter,
            can_use_ability=can_use_ability,
            can_play_item=can_play_item,
            can_end_turn=can_end_turn,
            can_play_stadium=can_play_stadium,
            can_play_pokemon=can_play_pokemon,
            attack_mask=attack_slots,
            bench_evolve_mask=bench_evolve,
            bench_retreat_mask=bench_retreat,
        )
