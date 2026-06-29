"""
Feature layout constants for the canonical game state encoder.

All dimensions are fixed so that the feature vector index of any field is
stable across states, game configurations, and code versions.  Downstream
components (policy networks, value heads) should import these constants
rather than hard-coding offsets.

Feature groups
--------------
ACTIVE_SELF       28    active Pokémon (current player)
BENCH_SELF       140    bench slots ×5 (current player)
HAND_SELF          7    hand summary (current player)
DECK_SELF          2    deck size / ratio
PRIZES_SELF        2    prizes remaining / ratio
DISCARD_SELF       2    discard size / ratio
LOST_ZONE_SELF     1    lost zone count (normalized)
ACTIVE_OPP        28    active Pokémon (opponent)
BENCH_OPP        140    bench slots ×5 (opponent)
HAND_OPP           1    hand count (opponent — hidden, count only)
DECK_OPP           2    deck size / ratio
PRIZES_OPP         2    prizes remaining / ratio
DISCARD_OPP        2    discard size / ratio
LOST_ZONE_OPP      1    lost zone count
STADIUM            1    stadium present flag
TURN               4    turn number, current player, supporter flag, energy flag
HISTORY          160    last 10 actions × (24 action-type one-hot + 1 player)
EMBEDDINGS       128    reserved for future learned card embeddings (all zeros)
─────────────────────
TOTAL            653
"""

from __future__ import annotations

from enum import Enum

# -------------------------------------------------------------------------
# Structural constants
# -------------------------------------------------------------------------

MAX_BENCH_SIZE: int = 5
MAX_HAND_SIZE: int = 20        # upper bound for normalization
MAX_DECK_SIZE: int = 60
MAX_PRIZES: int = 6
MAX_DAMAGE: int = 300          # upper bound for normalization
MAX_TURN: int = 100            # normalization denominator for turn number
MAX_RETREAT_COST: int = 5      # normalization denominator
HISTORY_LENGTH: int = 10       # number of recent actions to encode
NUM_ENERGY_TYPES: int = 11     # R W G L P F D M N C Y
NUM_SPECIAL_CONDITIONS: int = 5
NUM_ACTION_TYPES: int = 24     # len(ActionType.ordered())
NUM_STAGE_SLOTS: int = 4       # 0=basic/V, 1=stage1, 2=stage2/VMAX/VSTAR, 3=other

EMBEDDING_DIM: int = 128       # reserved placeholder dimension


# -------------------------------------------------------------------------
# Per-Pokémon feature layout (28 features)
# -------------------------------------------------------------------------
# [0]      present (1 if slot occupied)
# [1]      hp_ratio
# [2]      damage_ratio  (damage_taken / max_hp)
# [3..13]  energy counts by type (11 slots: R W G L P F D M N C Y)
# [14..18] special conditions one-hot (burned/poisoned/paralyzed/confused/asleep)
# [19]     retreat cost / MAX_RETREAT_COST
# [20]     has_attacked flag
# [21]     has_retreated flag
# [22]     prize_value / 2
# [23]     tool attached flag
# [24..27] stage one-hot (4 slots: basic/V, stage1, stage2/VMAX/VSTAR, other)

POKEMON_FEAT_SIZE: int = (
    1                           # present
    + 1                         # hp_ratio
    + 1                         # damage_ratio
    + NUM_ENERGY_TYPES          # energy counts
    + NUM_SPECIAL_CONDITIONS    # conditions
    + 1                         # retreat cost
    + 1                         # has_attacked
    + 1                         # has_retreated
    + 1                         # prize_value
    + 1                         # tool attached
    + NUM_STAGE_SLOTS           # stage one-hot
)
assert POKEMON_FEAT_SIZE == 28, f"Expected 28, got {POKEMON_FEAT_SIZE}"


# -------------------------------------------------------------------------
# Group sizes
# -------------------------------------------------------------------------

GROUP_ACTIVE_SIZE: int = POKEMON_FEAT_SIZE                    # 28
GROUP_BENCH_SIZE: int = POKEMON_FEAT_SIZE * MAX_BENCH_SIZE    # 140
GROUP_HAND_SIZE: int = 7   # count, energy, pokemon, item, supporter, stadium, tool
GROUP_DECK_SIZE: int = 2   # size/60, fraction
GROUP_PRIZES_SIZE: int = 2 # remaining/6, fraction
GROUP_DISCARD_SIZE: int = 2
GROUP_LOST_ZONE_SIZE: int = 1

GROUP_STADIUM_SIZE: int = 1
GROUP_TURN_SIZE: int = 4   # turn/100, current_player, supporter_played, energy_attached
GROUP_HISTORY_SIZE: int = HISTORY_LENGTH * (NUM_ACTION_TYPES + 1)  # 10 × 25 = 250
GROUP_EMBEDDING_SIZE: int = EMBEDDING_DIM                          # 128

# Full player block (self or opp)
PLAYER_SELF_SIZE: int = (
    GROUP_ACTIVE_SIZE + GROUP_BENCH_SIZE + GROUP_HAND_SIZE
    + GROUP_DECK_SIZE + GROUP_PRIZES_SIZE + GROUP_DISCARD_SIZE
    + GROUP_LOST_ZONE_SIZE
)  # 28 + 140 + 7 + 2 + 2 + 2 + 1 = 182

PLAYER_OPP_SIZE: int = (
    GROUP_ACTIVE_SIZE + GROUP_BENCH_SIZE
    + 1  # hand count only for opponent
    + GROUP_DECK_SIZE + GROUP_PRIZES_SIZE + GROUP_DISCARD_SIZE
    + GROUP_LOST_ZONE_SIZE
)  # 28 + 140 + 1 + 2 + 2 + 2 + 1 = 176

TOTAL_FEATURE_SIZE: int = (
    PLAYER_SELF_SIZE
    + PLAYER_OPP_SIZE
    + GROUP_STADIUM_SIZE
    + GROUP_TURN_SIZE
    + GROUP_HISTORY_SIZE
    + GROUP_EMBEDDING_SIZE
)
# 182 + 176 + 1 + 4 + 250 + 128 = 741


# -------------------------------------------------------------------------
# Group names (ordered, matches encoder output order)
# -------------------------------------------------------------------------

class FeatureGroup(str, Enum):
    ACTIVE_SELF = "active_self"
    BENCH_SELF = "bench_self"
    HAND_SELF = "hand_self"
    DECK_SELF = "deck_self"
    PRIZES_SELF = "prizes_self"
    DISCARD_SELF = "discard_self"
    LOST_ZONE_SELF = "lost_zone_self"
    ACTIVE_OPP = "active_opp"
    BENCH_OPP = "bench_opp"
    HAND_OPP = "hand_opp"
    DECK_OPP = "deck_opp"
    PRIZES_OPP = "prizes_opp"
    DISCARD_OPP = "discard_opp"
    LOST_ZONE_OPP = "lost_zone_opp"
    STADIUM = "stadium"
    TURN = "turn"
    HISTORY = "history"
    EMBEDDINGS = "embeddings"

    @classmethod
    def ordered(cls) -> tuple[FeatureGroup, ...]:
        return (
            cls.ACTIVE_SELF, cls.BENCH_SELF, cls.HAND_SELF,
            cls.DECK_SELF, cls.PRIZES_SELF, cls.DISCARD_SELF, cls.LOST_ZONE_SELF,
            cls.ACTIVE_OPP, cls.BENCH_OPP, cls.HAND_OPP,
            cls.DECK_OPP, cls.PRIZES_OPP, cls.DISCARD_OPP, cls.LOST_ZONE_OPP,
            cls.STADIUM, cls.TURN, cls.HISTORY, cls.EMBEDDINGS,
        )


GROUP_SIZES: dict[FeatureGroup, int] = {
    FeatureGroup.ACTIVE_SELF:    GROUP_ACTIVE_SIZE,
    FeatureGroup.BENCH_SELF:     GROUP_BENCH_SIZE,
    FeatureGroup.HAND_SELF:      GROUP_HAND_SIZE,
    FeatureGroup.DECK_SELF:      GROUP_DECK_SIZE,
    FeatureGroup.PRIZES_SELF:    GROUP_PRIZES_SIZE,
    FeatureGroup.DISCARD_SELF:   GROUP_DISCARD_SIZE,
    FeatureGroup.LOST_ZONE_SELF: GROUP_LOST_ZONE_SIZE,
    FeatureGroup.ACTIVE_OPP:     GROUP_ACTIVE_SIZE,
    FeatureGroup.BENCH_OPP:      GROUP_BENCH_SIZE,
    FeatureGroup.HAND_OPP:       1,
    FeatureGroup.DECK_OPP:       GROUP_DECK_SIZE,
    FeatureGroup.PRIZES_OPP:     GROUP_PRIZES_SIZE,
    FeatureGroup.DISCARD_OPP:    GROUP_DISCARD_SIZE,
    FeatureGroup.LOST_ZONE_OPP:  GROUP_LOST_ZONE_SIZE,
    FeatureGroup.STADIUM:        GROUP_STADIUM_SIZE,
    FeatureGroup.TURN:           GROUP_TURN_SIZE,
    FeatureGroup.HISTORY:        GROUP_HISTORY_SIZE,
    FeatureGroup.EMBEDDINGS:     GROUP_EMBEDDING_SIZE,
}

# Sanity check
_computed_total = sum(GROUP_SIZES.values())
assert _computed_total == TOTAL_FEATURE_SIZE, (
    f"GROUP_SIZES sum {_computed_total} != TOTAL_FEATURE_SIZE {TOTAL_FEATURE_SIZE}"
)


# -------------------------------------------------------------------------
# Group byte offsets (for slicing flat vector)
# -------------------------------------------------------------------------

def _compute_offsets() -> dict[FeatureGroup, tuple[int, int]]:
    offsets: dict[FeatureGroup, tuple[int, int]] = {}
    pos = 0
    for group in FeatureGroup.ordered():
        size = GROUP_SIZES[group]
        offsets[group] = (pos, pos + size)
        pos += size
    return offsets


GROUP_OFFSETS: dict[FeatureGroup, tuple[int, int]] = _compute_offsets()
