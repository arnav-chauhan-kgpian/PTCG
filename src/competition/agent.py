"""
CompetitionAgent — the public competition-mode entry point.

Usage::

    from src.competition import CompetitionAgent

    agent = CompetitionAgent.load("checkpoint.pt")     # or None for fresh net
    action = agent.choose_action(game_state)            # returns MCTSAction
    explanation = agent.last_explanation()              # optional

The agent owns:
  - a NetworkWrapper from CheckpointLoader
  - an InferenceEngine (NeuralEvaluator + NeuralPriorPolicy + cache)
  - a SimulatorProtocol (defaults to PokemonTCGSimulator)
  - an MCTSSearch reused across calls
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.competition.action_adapter import ActionAdapter
from src.competition.checkpoint_loader import CheckpointLoader
from src.competition.game_adapter import GameAdapter
from src.competition.inference_engine import InferenceEngine

if TYPE_CHECKING:
    from src.cards.repository import CardRepository
    from src.evaluation.explainability import DecisionExplanation
    from src.game_state.state import GameState
    from src.mcts.node import MCTSAction
    from src.mcts.simulation import SimulatorProtocol


@dataclass
class AgentConfig:
    iterations: int = 200
    time_budget_s: float = 5.0
    use_neural: bool = True
    cache_size: int = 50_000


class CompetitionAgent:
    """Pure-inference agent ready for tournament submission."""

    def __init__(
        self,
        *,
        simulator: SimulatorProtocol,
        inference: InferenceEngine | None = None,
        config: AgentConfig | None = None,
    ) -> None:
        from src.mcts import MCTSConfig, MCTSSearch
        self.simulator = simulator
        self.config = config or AgentConfig()
        self.inference = inference
        self._last_result = None
        self.action_adapter = ActionAdapter()
        self.game_adapter = GameAdapter()
        mcts_cfg = MCTSConfig(
            iterations=self.config.iterations,
            time_budget_s=self.config.time_budget_s,
        )
        if inference is not None and self.config.use_neural:
            self.search = MCTSSearch(
                simulator, config=mcts_cfg,
                evaluator=inference.evaluator,
                prior_policy=inference.prior_policy,
            )
        else:
            self.search = MCTSSearch(simulator, config=mcts_cfg)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def choose_action(self, state: GameState) -> MCTSAction:
        """Return the best action for *state*."""
        self.search.reset()
        result = self.search.run(state)
        self._last_result = result
        if result.best_action is None:
            # Fall back to first legal action when search produces nothing
            legal = self.simulator.legal_actions(state)
            return legal[0] if legal else None  # type: ignore[return-value]
        return result.best_action

    def choose_action_dict(self, state_dict: dict) -> dict:
        """Take a state dict, return an action dict (for REST / external use)."""
        state = self.game_adapter.from_dict(state_dict)
        action = self.choose_action(state)
        if action is None:
            return {"action_type": "end_turn", "details": {}}
        return self.action_adapter.to_dict(action)

    def last_explanation(self) -> DecisionExplanation | None:
        from src.evaluation.explainability import explain_decision
        if self._last_result is None:
            return None
        return explain_decision(
            self._last_result_state,  # type: ignore[attr-defined]
            self._last_result,
        )

    # ------------------------------------------------------------------ #
    # Factory
    # ------------------------------------------------------------------ #

    @classmethod
    def load(
        cls,
        checkpoint_path: str | None = None,
        *,
        repository: CardRepository | None = None,
        config: AgentConfig | None = None,
        device: str = "auto",
    ) -> CompetitionAgent:
        """Load a checkpoint and build a ready-to-use agent."""
        from src.simulator import PokemonTCGSimulator
        if repository is None:
            from src.cards import load_repository
            repository = load_repository()
        simulator = PokemonTCGSimulator(repository, seed=42)
        try:
            from src.mcts.network import has_torch
            if not has_torch():
                return cls(simulator=simulator, inference=None, config=config)
            loader = CheckpointLoader()
            loaded = loader.load(checkpoint_path, device=device)
            inference = InferenceEngine(loaded.network)
            return cls(simulator=simulator, inference=inference, config=config)
        except ImportError:
            return cls(simulator=simulator, inference=None, config=config)

    def summary(self) -> dict:
        return {
            "config": self.config.__dict__,
            "inference": self.inference.summary() if self.inference else None,
        }
