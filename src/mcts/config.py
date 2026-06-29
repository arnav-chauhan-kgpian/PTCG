"""
MCTS configuration — all tunable hyper-parameters in one place.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum


class SelectionStrategy(str, Enum):
    UCT = "uct"    # classic Upper Confidence Bound applied to Trees
    PUCT = "puct"  # polynomial UCT (AlphaZero style, uses neural prior)


class RolloutPolicy(str, Enum):
    RANDOM = "random"
    GREEDY = "greedy"
    HEURISTIC = "heuristic"       # evaluate leaf without rollout
    DEPTH_LIMITED = "depth_limited"


class ExpansionMode(str, Enum):
    ONE_AT_A_TIME = "one_at_a_time"  # classic MCTS
    FULL = "full"                     # expand all children immediately


@dataclass
class MCTSConfig:
    """
    Complete MCTS search configuration.

    Defaults are suitable for offline analysis with heuristic evaluation.
    Neural-network integration (Phase 9) should increase iterations and
    switch selection to PUCT.
    """

    # ── Stopping criteria ─────────────────────────────────────────────
    iterations: int = 800           # max simulations per search call
    time_budget_s: float = 2.0     # wall-clock time limit (seconds)
    max_nodes: int = 50_000        # memory guard

    # ── Selection ─────────────────────────────────────────────────────
    selection: SelectionStrategy = SelectionStrategy.UCT
    exploration_constant: float = math.sqrt(2)  # C in UCT; C_puct in PUCT
    add_dirichlet_noise: bool = False           # for root in self-play
    dirichlet_alpha: float = 0.3
    dirichlet_epsilon: float = 0.25

    # ── Expansion ─────────────────────────────────────────────────────
    expansion_mode: ExpansionMode = ExpansionMode.ONE_AT_A_TIME
    min_visits_to_expand: int = 1  # expand after this many visits

    # ── Rollout ───────────────────────────────────────────────────────
    rollout_policy: RolloutPolicy = RolloutPolicy.HEURISTIC
    rollout_depth: int = 10        # max depth for DEPTH_LIMITED rollout

    # ── Backpropagation ───────────────────────────────────────────────
    discount: float = 1.0          # temporal discount factor
    virtual_loss: float = 3.0      # applied during selection (parallel-ready)

    # ── Transposition table ───────────────────────────────────────────
    use_transposition: bool = True
    transposition_max_size: int = 100_000  # max entries (LRU eviction)

    # ── Determinization ───────────────────────────────────────────────
    determinizations: int = 1       # PIMC: samples of hidden info per search
    determinization_seed: int | None = None

    # ── Tree reuse ────────────────────────────────────────────────────
    reuse_tree: bool = True        # keep subtree for next move

    # ── Random seed (for reproducibility) ────────────────────────────
    seed: int | None = None

    def validate(self) -> None:
        assert self.iterations >= 1, "iterations must be >= 1"
        assert self.time_budget_s > 0, "time_budget_s must be > 0"
        assert self.exploration_constant >= 0, "exploration_constant must be >= 0"
        assert 0.0 <= self.discount <= 1.0, "discount must be in [0, 1]"
        assert self.virtual_loss >= 0, "virtual_loss must be >= 0"
        assert self.rollout_depth >= 0, "rollout_depth must be >= 0"
        assert self.determinizations >= 1, "determinizations must be >= 1"
        assert self.max_nodes >= 1, "max_nodes must be >= 1"

    @classmethod
    def fast(cls) -> MCTSConfig:
        """Minimal config for unit tests or time-critical contexts."""
        return cls(iterations=50, time_budget_s=0.1, max_nodes=5_000)

    @classmethod
    def default(cls) -> MCTSConfig:
        return cls()

    @classmethod
    def strong(cls) -> MCTSConfig:
        """High-iteration config for analysis."""
        return cls(
            iterations=4000,
            time_budget_s=10.0,
            max_nodes=200_000,
            rollout_policy=RolloutPolicy.HEURISTIC,
        )
