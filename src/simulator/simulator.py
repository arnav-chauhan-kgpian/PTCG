"""
PokemonTCGSimulator — the production simulator implementing SimulatorProtocol.

Usage::

    from src.cards import load_repository
    from src.simulator import PokemonTCGSimulator

    repo = load_repository()
    sim = PokemonTCGSimulator(repo, seed=42)
    state = sim.start_game(deck_a, deck_b)

    # MCTS / SelfPlay / Arena / TrainingPipeline can use `sim` unchanged
    while not sim.is_terminal(state):
        actions = sim.legal_actions(state)
        state = sim.apply_action(state, actions[0])

The simulator is stateful only for its internal RNG; ``apply_action`` is
otherwise a pure (state, action) → state transformation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.game_state.state import GameState
from src.game_state.zones import GameStatus
from src.mcts.node import MCTSAction
from src.simulator import executor
from src.simulator.legal_actions import legal_actions as _enumerate_legal
from src.simulator.randomizer import Randomizer
from src.simulator.rules import DEFAULT_RULES, GameRules
from src.simulator.setup import build_initial_state

if TYPE_CHECKING:
    from src.cards.repository import CardRepository


class PokemonTCGSimulator:
    """Concrete game engine satisfying ``mcts.SimulatorProtocol``."""

    def __init__(
        self,
        repository: CardRepository,
        *,
        rules: GameRules | None = None,
        seed: int | None = None,
    ) -> None:
        self.repository = repository
        self.rules = rules or DEFAULT_RULES
        self.randomizer = Randomizer(seed=seed)

    # ------------------------------------------------------------------ #
    # SimulatorProtocol
    # ------------------------------------------------------------------ #

    def legal_actions(self, state: GameState) -> list[MCTSAction]:
        return _enumerate_legal(state, self.repository, self.rules)

    def apply_action(self, state: GameState, action: MCTSAction) -> GameState:
        return executor.execute(state, action, self.repository, self.randomizer, self.rules)

    def is_terminal(self, state: GameState) -> bool:
        if state.game_status not in (GameStatus.NOT_STARTED, GameStatus.ONGOING):
            return True
        # Safety cap on game length
        if state.turn_number >= self.rules.max_turns:
            return True
        return False

    def terminal_value(self, state: GameState, player: int) -> float:
        """Outcome for *player*: 1.0 win, 0.0 loss, 0.5 draw/incomplete."""
        if state.game_status == GameStatus.DRAW:
            return 0.5
        if state.game_status == GameStatus.PLAYER_0_WIN:
            return 1.0 if player == 0 else 0.0
        if state.game_status == GameStatus.PLAYER_1_WIN:
            return 1.0 if player == 1 else 0.0
        # Ongoing or turn-capped: heuristic prize-based fallback
        p0_prizes = state.players[0].prizes_remaining
        p1_prizes = state.players[1].prizes_remaining
        raw = (p1_prizes - p0_prizes) / 6.0 + 0.5
        clamped = max(0.0, min(1.0, raw))
        return clamped if player == 0 else 1.0 - clamped

    # ------------------------------------------------------------------ #
    # Game lifecycle
    # ------------------------------------------------------------------ #

    def start_game(
        self, deck_a: list[int], deck_b: list[int]
    ) -> GameState:
        """Construct the initial GameState from two ordered card-ID decklists."""
        return build_initial_state(
            deck_a, deck_b, self.repository, self.randomizer, self.rules,
        )

    def reseed(self, seed: int) -> None:
        self.randomizer = Randomizer(seed=seed)
