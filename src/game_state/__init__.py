"""
Game State Representation & Feature Encoding Engine — Phase 7.

Public API::

    from src.game_state import (
        GameState, PlayerState, CardInstance,
        ActionRecord, ActionType, KnockoutRecord,
        ActionMask, FeatureEncoder, EncodedFeatures,
        Zone, SpecialCondition, GameStatus, CardCategory,
        EnergyTypeCode, PokemonStage,
        encode, encode_flat,
        validate_state, ValidationReport,
        to_terminal, to_markdown,
        state_fingerprint,
        serialization, exports, tensors,
    )
"""

# Enumerations
# Tensors
# Serialization
# Exports
from src.game_state import exports, serialization, tensors

# Actions & history
from src.game_state.actions import ActionRecord, ActionType, KnockoutRecord
from src.game_state.encoder import (
    DEFAULT_ENCODER,
    EncodedFeatures,
    FeatureEncoder,
    encode,
    encode_flat,
)
from src.game_state.exports import to_markdown, to_terminal

# Feature encoding
from src.game_state.features import (
    EMBEDDING_DIM,
    GROUP_OFFSETS,
    GROUP_SIZES,
    HISTORY_LENGTH,
    MAX_BENCH_SIZE,
    MAX_DECK_SIZE,
    MAX_PRIZES,
    NUM_ACTION_TYPES,
    NUM_ENERGY_TYPES,
    POKEMON_FEAT_SIZE,
    TOTAL_FEATURE_SIZE,
    FeatureGroup,
)

# Hashing
from src.game_state.hashing import (
    canonical_dict,
    instance_fingerprint,
    state_fingerprint,
    state_hash_int,
)
from src.game_state.history import GameHistory, make_action

# Action masks
from src.game_state.masks import TOTAL_MASK_SIZE, ActionMask

# Core models
from src.game_state.models import CardInstance, EnergyAttachment

# Player & game state
from src.game_state.player import PlayerState
from src.game_state.serialization import (
    StateSnapshot,
    from_bytes,
    from_dict,
    from_json,
    to_bytes,
    to_dict,
    to_json,
)
from src.game_state.state import GameState

# Validation
from src.game_state.validators import (
    ValidationIssue,
    ValidationReport,
    validate_state,
)
from src.game_state.zones import (
    CardCategory,
    EnergyTypeCode,
    GameStatus,
    PokemonStage,
    SpecialCondition,
    Zone,
)

__all__ = [
    # Enumerations
    "Zone", "SpecialCondition", "GameStatus", "CardCategory",
    "EnergyTypeCode", "PokemonStage",
    # Models
    "CardInstance", "EnergyAttachment",
    # Actions
    "ActionType", "ActionRecord", "KnockoutRecord",
    "GameHistory", "make_action",
    # State
    "PlayerState", "GameState",
    # Features
    "FeatureGroup", "GROUP_SIZES", "GROUP_OFFSETS",
    "TOTAL_FEATURE_SIZE", "POKEMON_FEAT_SIZE",
    "MAX_BENCH_SIZE", "MAX_DECK_SIZE", "MAX_PRIZES",
    "NUM_ENERGY_TYPES", "NUM_ACTION_TYPES",
    "HISTORY_LENGTH", "EMBEDDING_DIM",
    # Encoder
    "FeatureEncoder", "EncodedFeatures",
    "encode", "encode_flat", "DEFAULT_ENCODER",
    # Masks
    "ActionMask", "TOTAL_MASK_SIZE",
    # Hashing
    "state_fingerprint", "state_hash_int",
    "canonical_dict", "instance_fingerprint",
    # Serialization
    "to_dict", "from_dict", "to_json", "from_json",
    "to_bytes", "from_bytes", "StateSnapshot",
    "serialization",
    # Validation
    "validate_state", "ValidationIssue", "ValidationReport",
    # Exports
    "to_terminal", "to_markdown", "exports", "tensors",
]
