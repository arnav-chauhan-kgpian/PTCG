"""
Arena — head-to-head match play between two ``NetworkWrapper`` checkpoints.

Each side plays through ``MCTSSearch`` backed by ``NeuralEvaluator``.  No
training happens here; the arena just plays games and reports outcomes.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from src.mcts.config import MCTSConfig
from src.mcts.features import GameStateFeatureEncoder
from src.mcts.inference_cache import InferenceCache
from src.mcts.neural_evaluator import NeuralEvaluator
from src.mcts.neural_policy import NeuralPriorPolicy
from src.mcts.search import MCTSSearch

if TYPE_CHECKING:
    from src.game_state.state import GameState
    from src.mcts.features import FeatureEncoderProtocol
    from src.mcts.network import NetworkWrapper
    from src.mcts.node import MCTSAction
    from src.mcts.simulation import SimulatorProtocol


# -------------------------------------------------------------------------
# Result containers
# -------------------------------------------------------------------------

@dataclass
class ArenaGame:
    winner: int | None                  # 0 = candidate, 1 = champion, None = draw
    moves: int
    value_predictions: list[float] = field(default_factory=list)
    move_agreement: int = 0


@dataclass
class ArenaResult:
    candidate_wins: int = 0
    champion_wins: int = 0
    draws: int = 0
    games: list[ArenaGame] = field(default_factory=list)
    avg_value_error: float = 0.0
    avg_game_length: float = 0.0
    move_agreement_rate: float = 0.0
    elapsed_s: float = 0.0

    @property
    def total(self) -> int:
        return self.candidate_wins + self.champion_wins + self.draws

    @property
    def candidate_win_rate(self) -> float:
        decisive = self.candidate_wins + self.champion_wins
        if decisive == 0:
            return 0.5
        return self.candidate_wins / decisive

    @property
    def candidate_score(self) -> float:
        """Score = wins + 0.5 * draws (chess-style)."""
        return (self.candidate_wins + 0.5 * self.draws) / max(self.total, 1)

    def summary(self) -> dict:
        return {
            "total": self.total,
            "candidate_wins": self.candidate_wins,
            "champion_wins": self.champion_wins,
            "draws": self.draws,
            "candidate_win_rate": round(self.candidate_win_rate, 4),
            "candidate_score": round(self.candidate_score, 4),
            "avg_game_length": round(self.avg_game_length, 2),
            "avg_value_error": round(self.avg_value_error, 4),
            "move_agreement_rate": round(self.move_agreement_rate, 4),
            "elapsed_s": round(self.elapsed_s, 2),
        }


# -------------------------------------------------------------------------
# Arena engine
# -------------------------------------------------------------------------

class Arena:
    """
    Plays N games between two networks.  Side assignment alternates so
    both networks play as P0 and P1 equally.
    """

    def __init__(
        self,
        simulator: SimulatorProtocol,
        encoder: FeatureEncoderProtocol | None = None,
        action_map: list[MCTSAction] | None = None,
        mcts_config: MCTSConfig | None = None,
        seed: int | None = None,
    ) -> None:
        self.simulator = simulator
        self.encoder = encoder or GameStateFeatureEncoder()
        self.action_map = action_map or []
        self.mcts_config = mcts_config or MCTSConfig(
            iterations=40, time_budget_s=2.0
        )
        self._rng = random.Random(seed)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def play(
        self,
        candidate: NetworkWrapper,
        champion: NetworkWrapper,
        initial_state: GameState,
        n_games: int = 10,
        max_moves: int = 100,
    ) -> ArenaResult:
        result = ArenaResult()
        t0 = time.perf_counter()
        value_errors: list[float] = []

        cand_cache = InferenceCache()
        champ_cache = InferenceCache()

        for i in range(n_games):
            # Alternate which network plays player 0
            candidate_is_p0 = (i % 2 == 0)
            game = self._play_one(
                candidate, champion, candidate_is_p0,
                cand_cache, champ_cache,
                initial_state, max_moves,
            )
            result.games.append(game)
            if game.winner is None:
                result.draws += 1
            elif game.winner == 0:
                result.candidate_wins += 1
            else:
                result.champion_wins += 1
            value_errors.extend(game.value_predictions)

        result.elapsed_s = time.perf_counter() - t0
        if result.games:
            result.avg_game_length = sum(g.moves for g in result.games) / len(result.games)
            agree = sum(g.move_agreement for g in result.games)
            total_moves = sum(g.moves for g in result.games)
            result.move_agreement_rate = agree / max(total_moves, 1)
        if value_errors:
            result.avg_value_error = sum(value_errors) / len(value_errors)
        return result

    # ------------------------------------------------------------------ #
    # Single game
    # ------------------------------------------------------------------ #

    def _play_one(
        self,
        candidate: NetworkWrapper,
        champion: NetworkWrapper,
        candidate_is_p0: bool,
        cand_cache: InferenceCache,
        champ_cache: InferenceCache,
        initial_state: GameState,
        max_moves: int,
    ) -> ArenaGame:
        # Build a search per side, each with its own evaluator/policy/cache
        cand_search = self._make_search(candidate, cand_cache)
        champ_search = self._make_search(champion, champ_cache)

        state = initial_state
        moves = 0
        value_errors: list[float] = []
        agree = 0

        for move_num in range(max_moves):
            if self.simulator.is_terminal(state):
                break

            cur = state.current_player
            if (cur == 0 and candidate_is_p0) or (cur == 1 and not candidate_is_p0):
                primary = cand_search
                other = champ_search
            else:
                primary = champ_search
                other = cand_search

            primary_result = primary.run(state)
            chosen = primary_result.best_action
            if chosen is None:
                break

            # Move agreement: did the other network also rank chosen highest?
            try:
                other_result = other.run(state)
                if other_result.best_action == chosen:
                    agree += 1
            except Exception:
                pass

            # Value-prediction error: |v_pred − terminal_value(state, cur)| later
            # Instead we record best Q estimate from primary search
            if primary_result.action_ranking:
                top_visits = primary_result.action_ranking[0][1]
                value_errors.append(abs(0.5 - (top_visits / max(primary_result.total_visits, 1))))

            state = self.simulator.apply_action(state, chosen)
            moves += 1
            primary.reset()
            other.reset()

        terminal_value = self.simulator.terminal_value(state, 0)
        # winner from candidate's perspective
        if terminal_value > 0.5:
            cand_winner = 0 if candidate_is_p0 else 1
            winner = 0 if cand_winner == 0 else 1
        elif terminal_value < 0.5:
            cand_winner = 1 if candidate_is_p0 else 0
            winner = 0 if cand_winner == 0 else 1
        else:
            winner = None

        return ArenaGame(
            winner=winner,
            moves=moves,
            value_predictions=value_errors,
            move_agreement=agree,
        )

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _make_search(
        self, network: NetworkWrapper, cache: InferenceCache
    ) -> MCTSSearch:
        evaluator = NeuralEvaluator(network, self.encoder, self.action_map, cache)
        policy = NeuralPriorPolicy(network, self.encoder, self.action_map, cache)
        return MCTSSearch(
            self.simulator, config=self.mcts_config,
            evaluator=evaluator, prior_policy=policy,
        )
