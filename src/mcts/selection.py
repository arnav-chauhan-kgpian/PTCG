"""
Selection strategies — UCT and PUCT.

The selection phase descends the tree from the root, choosing the child
with the highest selection score at each level, until a leaf is reached.

UCT (Auer et al. 2002)
    score = Q(s,a) + C * sqrt(ln N(s) / N(s,a))

PUCT (Rosin 2011 / AlphaZero)
    score = Q(s,a) + C * P(s,a) * sqrt(N(s)) / (1 + N(s,a))

Both support virtual loss for future parallel execution.
"""

from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

from src.mcts.node import MCTSNode

if TYPE_CHECKING:
    from src.mcts.config import MCTSConfig


# -------------------------------------------------------------------------
# Score computation
# -------------------------------------------------------------------------

def uct_score(
    parent_visits: int,
    child_visits: int,
    child_value: float,
    child_prior: float,          # unused for UCT but kept in signature for API parity
    exploration_constant: float,
    *,
    virtual_loss: float = 0.0,
) -> float:
    """
    Upper Confidence Bound applied to Trees (UCT).

    Returns −∞ for unvisited children so they are always tried first.
    """
    if child_visits == 0:
        return math.inf
    exploit = child_value
    explore = exploration_constant * math.sqrt(math.log(parent_visits + 1) / child_visits)
    return exploit + explore - virtual_loss


def puct_score(
    parent_visits: int,
    child_visits: int,
    child_value: float,
    child_prior: float,
    exploration_constant: float,
    *,
    virtual_loss: float = 0.0,
) -> float:
    """
    Polynomial UCT (AlphaZero-style).

    Uses the prior probability P to weight the exploration bonus.
    When priors are uniform (1/n), PUCT degrades to UCT.
    """
    exploit = child_value
    explore = (
        exploration_constant
        * child_prior
        * math.sqrt(parent_visits + 1)
        / (1 + child_visits)
    )
    return exploit + explore - virtual_loss


# -------------------------------------------------------------------------
# Selection strategies
# -------------------------------------------------------------------------

class UCTSelection:
    """Classic UCT selection with configurable exploration constant."""

    def __init__(
        self,
        exploration_constant: float = math.sqrt(2),
        virtual_loss: float = 3.0,
        rng: random.Random | None = None,
    ) -> None:
        self.c = exploration_constant
        self.vl = virtual_loss
        self._rng = rng or random.Random()

    def select_child(self, node: MCTSNode) -> MCTSNode:
        """
        Select the child with the highest UCT score.
        Ties broken randomly.
        """
        best_score = -math.inf
        best: list[MCTSNode] = []

        parent_n = node.visit_count or 1

        for child in node.children.values():
            score = uct_score(
                parent_n,
                child.visit_count,
                child.adjusted_q,
                child.prior,
                self.c,
                virtual_loss=child.virtual_loss / max(child.visit_count + child.virtual_loss_count, 1),
            )
            if score > best_score:
                best_score = score
                best = [child]
            elif score == best_score:
                best.append(child)

        return self._rng.choice(best)


class PUCTSelection:
    """PUCT selection (AlphaZero-style, uses prior probabilities)."""

    def __init__(
        self,
        exploration_constant: float = 1.0,
        virtual_loss: float = 3.0,
        rng: random.Random | None = None,
    ) -> None:
        self.c = exploration_constant
        self.vl = virtual_loss
        self._rng = rng or random.Random()

    def select_child(self, node: MCTSNode) -> MCTSNode:
        best_score = -math.inf
        best: list[MCTSNode] = []

        parent_n = node.visit_count or 1

        for child in node.children.values():
            score = puct_score(
                parent_n,
                child.visit_count,
                child.adjusted_q,
                child.prior,
                self.c,
                virtual_loss=child.virtual_loss / max(child.visit_count + child.virtual_loss_count, 1),
            )
            if score > best_score:
                best_score = score
                best = [child]
            elif score == best_score:
                best.append(child)

        return self._rng.choice(best)


# -------------------------------------------------------------------------
# Tree descent (full selection phase)
# -------------------------------------------------------------------------

def select_leaf(
    root: MCTSNode,
    strategy: UCTSelection | PUCTSelection,
    virtual_loss_amount: float = 0.0,
) -> tuple[MCTSNode, list[MCTSNode]]:
    """
    Descend from root to a leaf node, applying virtual loss along the path.

    Returns
    -------
    leaf : MCTSNode
        The selected leaf (has untried actions or is terminal/unexpanded).
    path : list[MCTSNode]
        All nodes visited (root … leaf), for backpropagation.
    """
    path: list[MCTSNode] = [root]
    node = root

    if virtual_loss_amount > 0:
        node.apply_virtual_loss(virtual_loss_amount)

    while (
        node.is_fully_expanded
        and not node.is_terminal
        and node.children
    ):
        node = strategy.select_child(node)
        if virtual_loss_amount > 0:
            node.apply_virtual_loss(virtual_loss_amount)
        path.append(node)

    return node, path


def make_selection_strategy(config: MCTSConfig, rng: random.Random | None = None):
    """Factory: return the correct selection strategy from config."""
    from src.mcts.config import SelectionStrategy
    if config.selection == SelectionStrategy.UCT:
        return UCTSelection(
            exploration_constant=config.exploration_constant,
            virtual_loss=config.virtual_loss,
            rng=rng,
        )
    return PUCTSelection(
        exploration_constant=config.exploration_constant,
        virtual_loss=config.virtual_loss,
        rng=rng,
    )
