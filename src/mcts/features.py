"""
Feature encoder interface for the MCTS neural layer.

The MCTS neural components (network, evaluator, policy, inference cache)
all consume game states through a single ``FeatureEncoderProtocol``.
This keeps MCTS game-agnostic: any encoder that turns a state into a
fixed-length float vector can be plugged in.

The default ``GameStateFeatureEncoder`` wraps Phase 7's ``FeatureEncoder``
(741-dim canonical encoding).  ``IdentityFeatureEncoder`` is provided for
unit-testing the neural plumbing in isolation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from src.game_state.state import GameState


# -------------------------------------------------------------------------
# Protocol
# -------------------------------------------------------------------------

@runtime_checkable
class FeatureEncoderProtocol(Protocol):
    """
    Encode a GameState (or any opaque state object) into a flat tuple of
    floats suitable for neural inference.

    Implementations must be:
      • deterministic — same state → same vector
      • pure — never mutate the input
      • fixed-size — every encode() returns the same length
    """

    @property
    def feature_size(self) -> int: ...

    def encode(self, state: GameState) -> tuple[float, ...]: ...

    def decode(self, vector: tuple[float, ...]) -> GameState | None:
        """Optional reverse mapping (most encoders return None)."""
        ...


# -------------------------------------------------------------------------
# GameState encoder (production)
# -------------------------------------------------------------------------

class GameStateFeatureEncoder:
    """
    Wraps Phase 7 ``FeatureEncoder`` to expose the canonical 741-dim vector.

    The perspective defaults to ``-1`` (use ``state.current_player``).
    """

    def __init__(self, perspective: int = -1) -> None:
        from src.game_state.encoder import DEFAULT_ENCODER
        from src.game_state.features import TOTAL_FEATURE_SIZE
        self._encoder = DEFAULT_ENCODER
        self._size = TOTAL_FEATURE_SIZE
        self._perspective = perspective

    @property
    def feature_size(self) -> int:
        return self._size

    def encode(self, state: GameState) -> tuple[float, ...]:
        return self._encoder.encode_flat(state, self._perspective)

    def decode(self, vector: tuple[float, ...]) -> GameState | None:
        return None  # Phase 7 encoding is lossy


# -------------------------------------------------------------------------
# Identity encoder (testing)
# -------------------------------------------------------------------------

class IdentityFeatureEncoder:
    """
    Hash-based identity encoder for tests.

    Encodes a state to a deterministic but lossy vector derived from its
    SHA-256 fingerprint.  Useful for verifying network/cache plumbing
    without paying the full encoding cost.
    """

    def __init__(self, size: int = 16) -> None:
        self._size = size

    @property
    def feature_size(self) -> int:
        return self._size

    def encode(self, state) -> tuple[float, ...]:
        # State may not be a real GameState in tests — fall back to repr hash
        try:
            from src.game_state.hashing import state_fingerprint
            fp = state_fingerprint(state)
        except Exception:
            import hashlib
            fp = hashlib.sha256(repr(state).encode("utf-8")).hexdigest()
        # Map hex digits into [0, 1] floats
        out: list[float] = []
        for i in range(self._size):
            byte = int(fp[(i * 2) % len(fp): (i * 2) % len(fp) + 2], 16)
            out.append(byte / 255.0)
        return tuple(out)

    def decode(self, vector: tuple[float, ...]) -> object | None:
        return None


# -------------------------------------------------------------------------
# Factory
# -------------------------------------------------------------------------

def make_feature_encoder(name: str = "gamestate", **kwargs) -> FeatureEncoderProtocol:
    if name == "gamestate":
        return GameStateFeatureEncoder(**kwargs)
    if name == "identity":
        return IdentityFeatureEncoder(**kwargs)
    raise ValueError(f"Unknown encoder: {name!r}")
