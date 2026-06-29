"""
Convert between competition-format actions and ``MCTSAction``.

Competition envelopes are dicts of the shape::

    {"action_type": "attack", "details": {"slot": 0}}

This module provides round-trip conversion so external tournament
runners can interoperate without importing the MCTS module directly.
"""

from __future__ import annotations

from typing import Any

from src.mcts.node import MCTSAction


class ActionAdapter:
    """Codec between ``MCTSAction`` and JSON-serialisable dicts."""

    def to_dict(self, action: MCTSAction) -> dict[str, Any]:
        return {
            "action_type": action.action_type,
            "details": dict(action.details),
        }

    def from_dict(self, payload: dict[str, Any]) -> MCTSAction:
        action_type = str(payload.get("action_type", ""))
        details_raw = payload.get("details") or {}
        details = tuple(sorted((str(k), str(v)) for k, v in details_raw.items()))
        return MCTSAction(action_type=action_type, details=details)
