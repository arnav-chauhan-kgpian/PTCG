"""
MCTSSearch — the top-level orchestrator that ties the whole search together.

This is the public entry point for Phase 8 MCTS.  It coordinates:

    selection → expansion → evaluation/rollout → backpropagation

across multiple determinizations and aggregates results.

Usage::

    search = MCTSSearch(simulator, config=MCTSConfig())
    result = search.run(initial_state)
    print(result.best_action, result.statistics.to_dict())

The simulator is injected; MCTS itself never implements game rules.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.mcts.backpropagation import backpropagate
from src.mcts.config import (
    MCTSConfig,
)
from src.mcts.determinization import (
    DeterminizationSampler,
    IdentityDeterminizer,
    RandomDeterminizer,
)
from src.mcts.evaluator import (
    EvaluatorProtocol,
    HeuristicEvaluator,
)
from src.mcts.expansion import (
    add_dirichlet_noise,
    expand_all,
    expand_one,
)
from src.mcts.node import MCTSAction, MCTSNode
from src.mcts.policies import (
    PriorPolicy,
    UniformPriorPolicy,
)
from src.mcts.rollout import (
    RolloutBase,
    make_rollout,
)
from src.mcts.scheduler import SearchScheduler
from src.mcts.selection import (
    make_selection_strategy,
    select_leaf,
)
from src.mcts.statistics import SearchStatistics, timer
from src.mcts.transposition import TranspositionTable
from src.mcts.tree import MCTSTree

if TYPE_CHECKING:
    from src.game_state.state import GameState
    from src.mcts.simulation import SimulatorProtocol


# -------------------------------------------------------------------------
# Result container
# -------------------------------------------------------------------------

@dataclass
class SearchResult:
    """Complete output of a single MCTS search call."""

    best_action: MCTSAction | None
    visit_counts: dict[MCTSAction, int]
    action_ranking: list[tuple[MCTSAction, float]]
    principal_variation: list[MCTSAction]
    statistics: SearchStatistics
    tree_summary: dict
    elapsed_s: float

    @property
    def total_visits(self) -> int:
        return sum(self.visit_counts.values())

    def policy_distribution(self) -> dict[MCTSAction, float]:
        """Visit-count distribution (a 'soft' policy)."""
        total = max(self.total_visits, 1)
        return {a: v / total for a, v in self.visit_counts.items()}

    def to_dict(self) -> dict:
        return {
            "best_action": str(self.best_action) if self.best_action else None,
            "visit_counts": {str(a): v for a, v in self.visit_counts.items()},
            "action_ranking": [(str(a), round(s, 4)) for a, s in self.action_ranking],
            "principal_variation": [str(a) for a in self.principal_variation],
            "statistics": self.statistics.to_dict(),
            "tree_summary": self.tree_summary,
            "elapsed_s": round(self.elapsed_s, 4),
        }


# -------------------------------------------------------------------------
# Top-level search
# -------------------------------------------------------------------------

class MCTSSearch:
    """
    Orchestrates a complete MCTS search using the canonical four phases.

    The search is purely generic over the simulator interface: swapping in
    a different simulator or evaluator does not require touching this class.
    """

    def __init__(
        self,
        simulator: SimulatorProtocol,
        config: MCTSConfig | None = None,
        evaluator: EvaluatorProtocol | None = None,
        rollout: RolloutBase | None = None,
        prior_policy: PriorPolicy | None = None,
        determinizer: DeterminizationSampler | None = None,
        transposition: TranspositionTable | None = None,
    ) -> None:
        self.simulator = simulator
        self.config = config or MCTSConfig()
        self.config.validate()

        self.evaluator: EvaluatorProtocol = evaluator or HeuristicEvaluator()
        self.rollout: RolloutBase = rollout or make_rollout(
            self.config.rollout_policy, depth=self.config.rollout_depth,
        )
        self.prior_policy: PriorPolicy = prior_policy or UniformPriorPolicy()
        self.determinizer: DeterminizationSampler = determinizer or (
            RandomDeterminizer() if self.config.determinizations > 1
            else IdentityDeterminizer()
        )

        self.transposition: TranspositionTable | None = transposition
        if self.transposition is None and self.config.use_transposition:
            self.transposition = TranspositionTable(
                max_size=self.config.transposition_max_size
            )

        # Reusable tree across calls
        self._reusable_tree: MCTSTree | None = None

        # RNG
        self._rng = random.Random(self.config.seed)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def run(self, initial_state: GameState) -> SearchResult:
        """
        Run MCTS from *initial_state* and return the best action found.

        If multiple determinizations are configured, each is searched
        independently and visit counts are summed across them (PIMC).
        """
        n = self.config.determinizations
        states = self.determinizer.sample_n(initial_state, n, self._rng) if n > 1 else [initial_state]

        t0 = time.perf_counter()

        # First (or only) determinization is the canonical tree
        tree = self._make_tree(states[0])
        stats = SearchStatistics()
        self._search_one(tree, states[0], stats)

        # Additional determinizations: search and merge visit counts
        for extra_state in states[1:]:
            extra_tree = self._make_tree(extra_state)
            self._search_one(extra_tree, extra_state, stats)
            self._merge_visits(tree.root, extra_tree.root)

        stats.total_time_s = time.perf_counter() - t0
        if self.transposition is not None:
            stats.transposition_hits = self.transposition.stats.hits
            stats.transposition_misses = self.transposition.stats.misses

        return self._build_result(tree, stats, stats.total_time_s)

    def reset(self) -> None:
        """Clear reusable tree and transposition table."""
        self._reusable_tree = None
        if self.transposition is not None:
            self.transposition.clear()

    # ------------------------------------------------------------------ #
    # Core search loop
    # ------------------------------------------------------------------ #

    def _search_one(
        self,
        tree: MCTSTree,
        root_state: GameState,
        stats: SearchStatistics,
    ) -> None:
        """Run the iteration loop on a single tree."""
        scheduler = SearchScheduler.from_config(self.config).start()
        selection_strategy = make_selection_strategy(self.config, self._rng)

        # Initialise root with legal actions and priors
        if not tree.root.is_expanded:
            self._initialise(tree.root, stats)
            if self.config.add_dirichlet_noise:
                # Expand all root children so noise can apply across them
                with timer("expansion_time_s", stats):
                    children = expand_all(tree.root, self.simulator, self.transposition)
                stats.nodes_created += len(children)
                add_dirichlet_noise(
                    tree.root,
                    self.config.dirichlet_alpha,
                    self.config.dirichlet_epsilon,
                    self._rng,
                )

        while scheduler.should_continue():
            if tree.node_count >= self.config.max_nodes:
                break

            # 1. Selection
            with timer("selection_time_s", stats):
                leaf, path = select_leaf(
                    tree.root, selection_strategy,
                    virtual_loss_amount=self.config.virtual_loss,
                )

            # 2. Expansion (lazy)
            with timer("expansion_time_s", stats):
                if not leaf.is_expanded:
                    self._initialise(leaf, stats)

                if leaf.has_untried and not leaf.is_terminal:
                    child = expand_one(leaf, self.simulator, self.transposition)
                    if child is not None:
                        tree.register_node(child)
                        stats.nodes_created += 1
                        path.append(child)
                        leaf = child

            # 3. Evaluation / rollout
            with timer("evaluation_time_s", stats):
                value = self._evaluate(leaf, stats)
                stats.record_value(value)

            # 4. Backpropagation
            with timer("backprop_time_s", stats):
                backpropagate(
                    path, value,
                    discount=self.config.discount,
                    virtual_loss_amount=self.config.virtual_loss,
                )
                stats.backprop_steps += len(path)

            scheduler.tick()
            stats.iterations += 1

    def _initialise(self, node: MCTSNode, stats: SearchStatistics) -> None:
        if node.is_expanded:
            return
        actions = self.simulator.legal_actions(node.state)
        priors = self.prior_policy.prior_distribution(node.state, actions)
        node.set_legal_actions(actions, priors)
        stats.nodes_expanded += 1

    def _evaluate(self, node: MCTSNode, stats: SearchStatistics) -> float:
        if self.simulator.is_terminal(node.state):
            return self.simulator.terminal_value(node.state, node.player)
        value = self.rollout.rollout(
            node, self.simulator, self.evaluator,
            self._rng, self.config.rollout_depth,
        )
        stats.evaluations += 1
        return value

    # ------------------------------------------------------------------ #
    # Tree construction / reuse
    # ------------------------------------------------------------------ #

    def _make_tree(self, root_state: GameState) -> MCTSTree:
        if self.config.reuse_tree and self._reusable_tree is not None:
            return self._reusable_tree
        tree = MCTSTree(root_state)
        if self.config.reuse_tree:
            self._reusable_tree = tree
        return tree

    def _merge_visits(self, dest: MCTSNode, src: MCTSNode) -> None:
        """Merge child visit counts from *src* into *dest* (PIMC aggregation)."""
        for action, src_child in src.children.items():
            dest_child = dest.children.get(action)
            if dest_child is None:
                continue
            dest_child.visit_count += src_child.visit_count
            dest_child.total_value += src_child.total_value

    # ------------------------------------------------------------------ #
    # Result building
    # ------------------------------------------------------------------ #

    def _build_result(
        self,
        tree: MCTSTree,
        stats: SearchStatistics,
        elapsed: float,
    ) -> SearchResult:
        best = tree.best_action() if tree.root.children else None
        visit_counts = {
            a: c.visit_count for a, c in tree.root.children.items()
        }
        ranking = tree.action_ranking(normalize=False)
        pv = tree.principal_variation(max_depth=8)

        return SearchResult(
            best_action=best,
            visit_counts=visit_counts,
            action_ranking=ranking,
            principal_variation=pv,
            statistics=stats,
            tree_summary=tree.summary(),
            elapsed_s=elapsed,
        )


# -------------------------------------------------------------------------
# Module-level convenience
# -------------------------------------------------------------------------

def search(
    state: GameState,
    simulator: SimulatorProtocol,
    config: MCTSConfig | None = None,
) -> SearchResult:
    """One-shot convenience wrapper for ad-hoc MCTS calls."""
    return MCTSSearch(simulator, config=config).run(state)
