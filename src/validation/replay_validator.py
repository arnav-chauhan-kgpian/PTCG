"""
ReplayValidator — replay a deterministic action sequence and assert the
final ``GameState`` matches an expected fingerprint.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.game_state.state import GameState
    from src.mcts.node import MCTSAction
    from src.simulator import PokemonTCGSimulator


@dataclass
class ReplayResult:
    actions_applied: int = 0
    terminal_reached: bool = False
    final_fingerprint: str = ""
    matched: bool = False
    failure_index: int | None = None

    def to_dict(self) -> dict:
        return vars(self)


class ReplayValidator:
    """Replay scenarios — every step is verified to be a legal action."""

    def replay(
        self,
        simulator: PokemonTCGSimulator,
        initial_state: GameState,
        actions: list[MCTSAction],
        expected_fingerprint: str | None = None,
    ) -> ReplayResult:
        from src.game_state.hashing import state_fingerprint
        state = initial_state
        result = ReplayResult()
        for i, action in enumerate(actions):
            legal = simulator.legal_actions(state)
            if action not in legal:
                result.failure_index = i
                break
            state = simulator.apply_action(state, action)
            result.actions_applied += 1
            if simulator.is_terminal(state):
                result.terminal_reached = True
                break
        result.final_fingerprint = state_fingerprint(state)
        if expected_fingerprint is not None:
            result.matched = result.final_fingerprint == expected_fingerprint
        else:
            result.matched = result.failure_index is None
        return result
