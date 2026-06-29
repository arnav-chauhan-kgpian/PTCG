"""
Expansion — create child nodes from a leaf.

The expansion phase converts a leaf node's untried actions into real child
nodes by calling the simulator.  Prior probabilities from the evaluator
are assigned to each child at creation time.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from src.mcts.node import MCTSAction, MCTSNode

if TYPE_CHECKING:
    from src.mcts.simulation import SimulatorProtocol
    from src.mcts.transposition import TranspositionTable


def _normalise_priors(
    priors: dict[MCTSAction, float],
    actions: list[MCTSAction],
) -> dict[MCTSAction, float]:
    """Normalise and fill missing priors with a uniform default."""
    n = len(actions)
    if n == 0:
        return {}
    default = 1.0 / n
    filled = {a: priors.get(a, default) for a in actions}
    total = sum(filled.values())
    if total <= 0:
        return dict.fromkeys(actions, default)
    return {a: v / total for a, v in filled.items()}


def initialise_node(
    node: MCTSNode,
    simulator: SimulatorProtocol,
    priors: dict[MCTSAction, float] | None = None,
) -> None:
    """
    Compute legal actions for *node* and populate its untried list.

    Must be called exactly once per node before any child is expanded.
    """
    if node.is_expanded:
        return

    if node.is_terminal or simulator.is_terminal(node.state):
        node.is_terminal = True
        node.is_expanded = True
        return

    actions = simulator.legal_actions(node.state)
    if priors:
        norm = _normalise_priors(priors, actions)
    else:
        n = len(actions)
        norm = dict.fromkeys(actions, 1.0 / n) if n else {}

    node.set_legal_actions(actions, norm)


def expand_one(
    node: MCTSNode,
    simulator: SimulatorProtocol,
    transposition: TranspositionTable | None = None,
) -> MCTSNode | None:
    """
    Expand a single untried action from *node*, returning the new child.

    Returns None if there is nothing to expand (node is terminal or
    fully expanded).
    """
    if not node.has_untried:
        return None

    action = node.pop_untried()
    new_state = simulator.apply_action(node.state, action)

    # Check transposition table first
    if transposition is not None:
        existing = transposition.lookup_by_state(new_state)
        if existing is not None:
            node.add_child(action, existing)
            return existing

    child = MCTSNode(
        state=new_state,
        parent=node,
        action=action,
        depth=node.depth + 1,
    )
    node.add_child(action, child)

    if transposition is not None:
        transposition.insert(child)

    return child


def expand_all(
    node: MCTSNode,
    simulator: SimulatorProtocol,
    transposition: TranspositionTable | None = None,
) -> list[MCTSNode]:
    """
    Expand ALL untried actions at once (full expansion mode).

    Returns the list of newly created children.
    """
    children: list[MCTSNode] = []
    while node.has_untried:
        child = expand_one(node, simulator, transposition)
        if child is not None:
            children.append(child)
    return children


def add_dirichlet_noise(
    node: MCTSNode,
    alpha: float,
    epsilon: float,
    rng: random.Random | None = None,
) -> None:
    """
    Add Dirichlet noise to root node priors for self-play exploration.

    Standard AlphaZero: prior ← (1-ε)*prior + ε*η  where η~Dir(α)
    Only applied to the root node.
    """
    if not node.children:
        return
    rng = rng or random.Random()
    n = len(node.children)
    # Simple symmetric Dirichlet via gamma sampling
    gammas = [rng.gammavariate(alpha, 1.0) for _ in range(n)]
    total = sum(gammas)
    noise = [g / total for g in gammas]
    for (action, child), eta in zip(node.children.items(), noise):
        child.prior = (1 - epsilon) * child.prior + epsilon * eta
