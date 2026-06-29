"""
Convert between competition-format game states and ``GameState``.

For most competition harnesses the engine accepts our internal
``GameState`` directly; this adapter exists so external runners that emit
JSON envelopes can be plugged in without further changes.
"""

from __future__ import annotations

from typing import Any

from src.game_state.serialization import from_dict, to_dict
from src.game_state.state import GameState


class GameAdapter:
    """Codec between ``GameState`` and dict/JSON envelopes."""

    def to_dict(self, state: GameState) -> dict[str, Any]:
        return to_dict(state)

    def from_dict(self, payload: dict[str, Any]) -> GameState:
        return from_dict(payload)
