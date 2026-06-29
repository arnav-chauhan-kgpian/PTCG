"""
Serialization and deserialization for GameState.

Supported formats
-----------------
- dict        : nested Python dicts/lists (lossless, Pydantic-native)
- JSON str    : UTF-8 JSON string
- bytes       : gzip-compressed JSON (binary compact format)
- MessagePack : optional msgpack bytes (requires msgpack package)

All round-trips preserve structural equality:
    from_dict(to_dict(state)) == state
    from_json(to_json(state)) == state
    from_bytes(to_bytes(state)) == state
"""

from __future__ import annotations

import gzip
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.game_state.state import GameState

try:
    import msgpack as _msgpack
    _HAS_MSGPACK = True
except ImportError:
    _msgpack = None  # type: ignore[assignment]
    _HAS_MSGPACK = False


# -------------------------------------------------------------------------
# dict ↔ GameState
# -------------------------------------------------------------------------

def to_dict(state: GameState) -> dict[str, Any]:
    """Serialize to a nested dict using Pydantic's model_dump."""
    return state.model_dump()


def from_dict(data: dict[str, Any]) -> GameState:
    """Deserialize from a nested dict produced by to_dict."""
    from src.game_state.state import GameState
    return GameState.model_validate(data)


# -------------------------------------------------------------------------
# JSON ↔ GameState
# -------------------------------------------------------------------------

def to_json(state: GameState, indent: int | None = None) -> str:
    """Serialize to a JSON string."""
    return state.model_dump_json(indent=indent)


def from_json(text: str) -> GameState:
    """Deserialize from a JSON string produced by to_json."""
    from src.game_state.state import GameState
    return GameState.model_validate_json(text)


# -------------------------------------------------------------------------
# Binary (gzip-compressed JSON)
# -------------------------------------------------------------------------

def to_bytes(state: GameState) -> bytes:
    """Serialize to gzip-compressed JSON bytes (compact binary format)."""
    raw = state.model_dump_json().encode("utf-8")
    return gzip.compress(raw, compresslevel=6)


def from_bytes(data: bytes) -> GameState:
    """Deserialize from gzip bytes produced by to_bytes."""
    from src.game_state.state import GameState
    raw = gzip.decompress(data)
    return GameState.model_validate_json(raw.decode("utf-8"))


# -------------------------------------------------------------------------
# MessagePack (optional)
# -------------------------------------------------------------------------

def has_msgpack() -> bool:
    return _HAS_MSGPACK


def to_msgpack(state: GameState) -> bytes:
    """Serialize to MessagePack bytes (requires msgpack package)."""
    if not _HAS_MSGPACK:
        raise ImportError("msgpack is not installed. pip install msgpack")
    data = to_dict(state)
    return _msgpack.packb(data, use_bin_type=True)  # type: ignore[union-attr]


def from_msgpack(data: bytes) -> GameState:
    """Deserialize from MessagePack bytes."""
    if not _HAS_MSGPACK:
        raise ImportError("msgpack is not installed. pip install msgpack")
    raw = _msgpack.unpackb(data, raw=False)  # type: ignore[union-attr]
    return from_dict(raw)


# -------------------------------------------------------------------------
# File I/O
# -------------------------------------------------------------------------

def write_json(state: GameState, path, indent: int | None = 2) -> None:
    import pathlib
    pathlib.Path(path).write_text(to_json(state, indent=indent), encoding="utf-8")


def read_json(path) -> GameState:
    import pathlib
    return from_json(pathlib.Path(path).read_text(encoding="utf-8"))


def write_bytes(state: GameState, path) -> None:
    import pathlib
    pathlib.Path(path).write_bytes(to_bytes(state))


def read_bytes(path) -> GameState:
    import pathlib
    return from_bytes(pathlib.Path(path).read_bytes())


# -------------------------------------------------------------------------
# Snapshot registry (in-memory cache for MCTS / replay)
# -------------------------------------------------------------------------

class StateSnapshot:
    """
    Thin in-memory key→GameState cache keyed by state fingerprint.
    Useful for MCTS transposition tables and replay deduplication.
    """

    def __init__(self) -> None:
        self._store: dict[str, GameState] = {}

    def put(self, state: GameState) -> str:
        from src.game_state.hashing import state_fingerprint
        fp = state_fingerprint(state)
        self._store[fp] = state
        return fp

    def get(self, fingerprint: str) -> GameState | None:
        return self._store.get(fingerprint)

    def __contains__(self, fingerprint: str) -> bool:
        return fingerprint in self._store

    def __len__(self) -> int:
        return len(self._store)

    def clear(self) -> None:
        self._store.clear()
