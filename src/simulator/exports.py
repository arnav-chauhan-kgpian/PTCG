"""
Human-readable export formats for the simulator.
"""

from __future__ import annotations

from src.game_state.state import GameState


def to_terminal(state: GameState) -> str:
    """Compact one-screen game-state summary."""
    from src.game_state.exports import to_terminal as gs_terminal
    return gs_terminal(state)


def action_to_terminal(action) -> str:
    parts = [action.action_type]
    for k, v in action.details:
        parts.append(f"{k}={v}")
    return " ".join(parts)


def legal_actions_to_terminal(actions: list) -> str:
    lines = [f"Legal actions ({len(actions)}):"]
    for i, a in enumerate(actions[:30]):
        lines.append(f"  [{i:2d}] {action_to_terminal(a)}")
    if len(actions) > 30:
        lines.append(f"  ... ({len(actions) - 30} more)")
    return "\n".join(lines)
