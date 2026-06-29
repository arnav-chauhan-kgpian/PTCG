"""
Self-play game generation.

Plays a complete game by repeatedly running ``MCTSSearch`` for the moving
player, sampling an action from the resulting visit-count distribution,
and applying it through the injected simulator.  Each move is recorded as
a ``SelfPlayMove`` containing everything needed to construct training
samples after the game terminates.

The engine is **simulator-agnostic** — only ``SimulatorProtocol`` and
``MCTSSearch`` are required.  When a neural evaluator is plugged into the
search, self-play games drive the AlphaZero training loop; with the
heuristic evaluator it still produces valid (lower-quality) data.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from src.mcts.node import MCTSAction
from src.mcts.search import MCTSSearch
from src.mcts.training_targets import (
    TemperatureSchedule,
    TrainingSample,
    outcome_to_value_target,
    policy_to_vector,
    visit_counts_to_policy,
)

if TYPE_CHECKING:
    from src.game_state.state import GameState
    from src.mcts.features import FeatureEncoderProtocol
    from src.mcts.simulation import SimulatorProtocol


# -------------------------------------------------------------------------
# Containers
# -------------------------------------------------------------------------

@dataclass(frozen=True)
class SelfPlayMove:
    """One recorded ply of a self-play game."""
    turn: int
    player: int
    state_features: tuple[float, ...]
    policy: dict[MCTSAction, float]
    visit_counts: dict[MCTSAction, int]
    chosen_action: MCTSAction
    temperature: float


@dataclass
class SelfPlayGame:
    """A complete game played out by the self-play engine."""
    moves: list[SelfPlayMove] = field(default_factory=list)
    final_value: float = 0.5            # terminal value from P0 perspective
    winner: int | None = None
    move_count: int = 0
    terminated_by: str = "ongoing"      # "terminal" | "max_moves" | "no_actions"

    def to_training_samples(
        self, action_map: list[MCTSAction]
    ) -> list[TrainingSample]:
        samples: list[TrainingSample] = []
        for m in self.moves:
            value_target = outcome_to_value_target(
                self.final_value, m.player, self.winner
            )
            policy_vec = policy_to_vector(m.policy, action_map)
            samples.append(TrainingSample(
                state_features=m.state_features,
                policy_target=tuple(policy_vec),
                value_target=value_target,
                move_player=m.player,
                move_number=m.turn,
            ))
        return samples

    def summary(self) -> dict:
        return {
            "move_count": self.move_count,
            "winner": self.winner,
            "final_value": round(self.final_value, 4),
            "terminated_by": self.terminated_by,
        }


# -------------------------------------------------------------------------
# Engine
# -------------------------------------------------------------------------

class SelfPlayEngine:
    """
    Plays full games by alternating MCTS searches and applying the
    visit-distribution-sampled action.

    A single ``MCTSSearch`` instance is reused; the simulator drives state
    transitions.  The feature encoder must match the one the network was
    trained on so the recorded ``state_features`` align with future
    network inputs.
    """

    def __init__(
        self,
        simulator: SimulatorProtocol,
        search: MCTSSearch,
        feature_encoder: FeatureEncoderProtocol,
        temperature_schedule: TemperatureSchedule | None = None,
        max_moves: int = 200,
        seed: int | None = None,
    ) -> None:
        self.simulator = simulator
        self.search = search
        self.feature_encoder = feature_encoder
        self.temperature = temperature_schedule or TemperatureSchedule()
        self.max_moves = max_moves
        self._rng = random.Random(seed)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def play_game(self, initial_state: GameState) -> SelfPlayGame:
        """Play one complete game starting from *initial_state*."""
        game = SelfPlayGame()
        state = initial_state

        for move_num in range(self.max_moves):
            if self.simulator.is_terminal(state):
                game.terminated_by = "terminal"
                break

            result = self.search.run(state)
            if not result.visit_counts:
                game.terminated_by = "no_actions"
                break

            temperature = self.temperature.temperature_for(move_num)
            policy = visit_counts_to_policy(result.visit_counts, temperature)
            chosen = self._sample_action(policy)
            if chosen is None:
                game.terminated_by = "no_actions"
                break

            game.moves.append(SelfPlayMove(
                turn=state.turn_number,
                player=state.current_player,
                state_features=self.feature_encoder.encode(state),
                policy=dict(policy),
                visit_counts=dict(result.visit_counts),
                chosen_action=chosen,
                temperature=temperature,
            ))

            state = self.simulator.apply_action(state, chosen)

            # Reset search tree between moves (no tree reuse for now)
            self.search.reset()

        else:
            game.terminated_by = "max_moves"

        # Determine outcome (from player 0's perspective)
        game.final_value = self.simulator.terminal_value(state, 0)
        game.winner = self._winner_from(state)
        game.move_count = len(game.moves)
        return game

    def play_n_games(
        self, initial_state: GameState, n: int
    ) -> list[SelfPlayGame]:
        return [self.play_game(initial_state) for _ in range(n)]

    # ------------------------------------------------------------------ #
    # Internal
    # ------------------------------------------------------------------ #

    def _sample_action(
        self, policy: dict[MCTSAction, float]
    ) -> MCTSAction | None:
        if not policy:
            return None
        actions = list(policy.keys())
        weights = list(policy.values())
        total = sum(weights)
        if total <= 0:
            return self._rng.choice(actions)
        # Normalise (defensive) and sample
        weights = [w / total for w in weights]
        r = self._rng.random()
        cumulative = 0.0
        for action, w in zip(actions, weights):
            cumulative += w
            if r <= cumulative:
                return action
        return actions[-1]

    def _winner_from(self, state: GameState) -> int | None:
        from src.game_state.zones import GameStatus
        if state.game_status == GameStatus.PLAYER_0_WIN:
            return 0
        if state.game_status == GameStatus.PLAYER_1_WIN:
            return 1
        return None
