"""
Simulator protocol — the external interface MCTS uses to advance game states.

MCTS does not implement game rules.  Instead it delegates all state
transitions to an object that satisfies SimulatorProtocol.  A future
concrete simulator (Phase N) plugs in by implementing this interface.

This module also provides:
  • A NullSimulator for unit-testing the MCTS logic in isolation.
  • A typed Action ↔ ActionRecord bridge for seamless Phase 7 integration.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from src.mcts.node import MCTSAction

if TYPE_CHECKING:
    from src.game_state.state import GameState


# -------------------------------------------------------------------------
# Protocol
# -------------------------------------------------------------------------

@runtime_checkable
class SimulatorProtocol(Protocol):
    """
    Interface that any concrete PTCG simulator must satisfy.

    MCTS calls these methods during the search loop.  Implementations must
    be deterministic given the same inputs (after determinization sampling
    is applied externally by DeterminizationSampler).
    """

    def legal_actions(self, state: GameState) -> list[MCTSAction]:
        """
        Return all legal actions available to ``state.current_player``.
        Must always include at least ``end_turn`` unless the state is terminal.
        """
        ...

    def apply_action(
        self, state: GameState, action: MCTSAction
    ) -> GameState:
        """
        Return a new GameState after applying *action* to *state*.
        Must NOT mutate the input state.
        """
        ...

    def is_terminal(self, state: GameState) -> bool:
        """Return True if the game is over (no more actions meaningful)."""
        ...

    def terminal_value(self, state: GameState, player: int) -> float:
        """
        Return the outcome value for *player* in a terminal state.
        Convention: 1.0 = win, 0.0 = loss, 0.5 = draw.
        """
        ...


# -------------------------------------------------------------------------
# Null simulator (testing / placeholder)
# -------------------------------------------------------------------------

class NullSimulator:
    """
    Minimal simulator for unit-testing MCTS tree logic.

    States are represented by turn number only.  After MAX_TURNS turns the
    game ends.  On each turn the current player can choose from N_ACTIONS
    randomly generated actions.
    """

    MAX_TURNS: int = 20
    N_ACTIONS: int = 4

    def __init__(
        self,
        max_turns: int = MAX_TURNS,
        n_actions: int = N_ACTIONS,
        seed: int | None = None,
    ) -> None:
        self.max_turns = max_turns
        self.n_actions = n_actions
        self._rng = random.Random(seed)

    def legal_actions(self, state: GameState) -> list[MCTSAction]:
        if self.is_terminal(state):
            return []
        # Deterministic action set derived from turn number so the same
        # state always yields the same actions (needed for transposition table)
        actions = [
            MCTSAction(action_type=f"action_{i}", details=(("turn", str(state.turn_number)),))
            for i in range(self.n_actions)
        ]
        actions.append(MCTSAction.end_turn())
        return actions

    def apply_action(
        self, state: GameState, action: MCTSAction
    ) -> GameState:
        """Advance turn and flip current player."""
        from src.game_state.zones import GameStatus
        new_turn = state.turn_number + 1
        new_player = 1 - state.current_player

        # Check terminal
        if new_turn >= self.max_turns:
            new_status = GameStatus.PLAYER_0_WIN
        else:
            new_status = GameStatus.ONGOING

        return state.model_copy(update={
            "turn_number": new_turn,
            "current_player": new_player,
            "game_status": new_status,
        })

    def is_terminal(self, state: GameState) -> bool:
        from src.game_state.zones import GameStatus
        return (
            state.turn_number >= self.max_turns
            or state.game_status not in (GameStatus.NOT_STARTED, GameStatus.ONGOING)
        )

    def terminal_value(self, state: GameState, player: int) -> float:
        from src.game_state.zones import GameStatus
        if state.game_status == GameStatus.DRAW:
            return 0.5
        if state.game_status == GameStatus.PLAYER_0_WIN:
            return 1.0 if player == 0 else 0.0
        if state.game_status == GameStatus.PLAYER_1_WIN:
            return 1.0 if player == 1 else 0.0
        # Heuristic: turn-based with slight P0 advantage
        p0_prizes = state.players[0].prizes_remaining
        p1_prizes = state.players[1].prizes_remaining
        raw = (p1_prizes - p0_prizes) / 6.0 + 0.5
        return max(0.0, min(1.0, raw)) if player == 0 else 1.0 - max(0.0, min(1.0, raw))
