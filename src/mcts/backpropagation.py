"""
Backpropagation — propagate simulation values up the tree.

After each simulation the value is pushed from the leaf back to the root.
Player perspective alternates at each level: if the current node belongs
to player 0, its parent belongs to player 1 (and vice versa), so the
value is inverted when crossing a player boundary.

Equations
---------
For each node n on the path leaf … root:

    N(n) ← N(n) + 1
    W(n) ← W(n) + v_n
    Q(n) = W(n) / N(n)

where v_n = v if n.player == root_player else 1 − v (with discount).
"""

from __future__ import annotations

from src.mcts.node import MCTSNode


def backpropagate(
    path: list[MCTSNode],
    value: float,
    discount: float = 1.0,
    virtual_loss_amount: float = 0.0,
) -> None:
    """
    Walk *path* from leaf to root, updating visit counts and values.

    Parameters
    ----------
    path : list[MCTSNode]
        Nodes from root (index 0) to leaf (last index), inclusive.
    value : float
        Value in [0, 1] from the leaf node's player perspective.
    discount : float
        Temporal discount factor applied per step back towards root.
    virtual_loss_amount : float
        If > 0, undo the virtual loss that was applied during selection.
    """
    if not path:
        return

    leaf = path[-1]
    leaf_player = leaf.player
    current_discount = 1.0

    # Walk from leaf back to root
    for node in reversed(path):
        # Adjust value to this node's player perspective
        if node.player == leaf_player:
            v = value * current_discount
        else:
            v = (1.0 - value) * current_discount

        node.update(v)

        if virtual_loss_amount > 0:
            node.undo_virtual_loss(virtual_loss_amount)

        current_discount *= discount


def backpropagate_terminal(
    path: list[MCTSNode],
    value: float,
    discount: float = 1.0,
    virtual_loss_amount: float = 0.0,
) -> None:
    """
    Convenience wrapper for terminal node backpropagation.
    Identical to backpropagate but named explicitly for clarity.
    """
    backpropagate(path, value, discount, virtual_loss_amount)
