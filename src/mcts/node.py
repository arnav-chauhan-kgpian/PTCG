"""
MCTSNode and MCTSAction — the core data structures of the search tree.

MCTSAction is a lightweight hashable action for tree edges.
MCTSNode stores all MCTS statistics and tree topology for one game position.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.game_state.state import GameState


# -------------------------------------------------------------------------
# Action (tree edge label)
# -------------------------------------------------------------------------

@dataclass(frozen=True)
class MCTSAction:
    """
    Lightweight, hashable action for use as a tree edge label.

    Maps 1-to-1 with Phase 7 ActionRecord but avoids that module's
    overhead inside the hot search loop.
    """
    action_type: str
    card_instance_id: str | None = None
    target_instance_id: str | None = None
    details: tuple[tuple[str, str], ...] = ()

    def __str__(self) -> str:
        parts = [self.action_type]
        if self.card_instance_id:
            parts.append(self.card_instance_id[:8])
        for k, v in self.details:
            parts.append(f"{k}={v}")
        return ":".join(parts)

    @classmethod
    def end_turn(cls) -> MCTSAction:
        return cls(action_type="end_turn")

    @classmethod
    def attack(cls, card_id: str, attack_name: str) -> MCTSAction:
        return cls(
            action_type="attack",
            card_instance_id=card_id,
            details=(("attack", attack_name),),
        )

    @classmethod
    def play_pokemon(cls, card_id: str, target: str | None = None) -> MCTSAction:
        return cls(
            action_type="play_pokemon",
            card_instance_id=card_id,
            target_instance_id=target,
        )


# -------------------------------------------------------------------------
# Node
# -------------------------------------------------------------------------

_NODE_COUNTER = 0


def _next_node_id() -> int:
    global _NODE_COUNTER
    _NODE_COUNTER += 1
    return _NODE_COUNTER


def reset_node_counter() -> None:
    """Reset global node ID counter (call between tests)."""
    global _NODE_COUNTER
    _NODE_COUNTER = 0


class MCTSNode:
    """
    One node in the MCTS search tree.

    A node represents a game position (GameState) reached by a particular
    sequence of actions from the root.  All MCTS bookkeeping lives here.

    Statistics
    ----------
    visit_count (N)   : times this node has been part of a simulation
    total_value (W)   : cumulative value backpropagated through this node
    q_value (Q)       : W / N
    prior (P)         : prior probability from policy (placeholder = 1/n)
    virtual_loss      : temporary penalty applied during parallel selection
    """

    __slots__ = (
        "state", "parent", "action", "depth", "player",
        "node_id", "state_hash",
        "visit_count", "total_value", "prior",
        "virtual_loss", "virtual_loss_count",
        "children", "untried_actions",
        "is_expanded", "is_terminal",
    )

    def __init__(
        self,
        state: GameState,
        parent: MCTSNode | None = None,
        action: MCTSAction | None = None,
        depth: int = 0,
        prior: float = 1.0,
        state_hash: str | None = None,
    ) -> None:
        self.state = state
        self.parent = parent
        self.action = action
        self.depth = depth
        self.player = state.current_player
        self.prior = prior

        # Identity
        self.node_id: int = _next_node_id()
        if state_hash is not None:
            self.state_hash = state_hash
        else:
            from src.game_state.hashing import state_fingerprint
            self.state_hash = state_fingerprint(state)

        # Statistics
        self.visit_count: int = 0
        self.total_value: float = 0.0
        self.virtual_loss: float = 0.0
        self.virtual_loss_count: int = 0

        # Tree structure
        self.children: dict[MCTSAction, MCTSNode] = {}
        self.untried_actions: list[MCTSAction] = []
        self.is_expanded: bool = False
        self.is_terminal: bool = state.is_terminal

    # ------------------------------------------------------------------ #
    # Value accessors
    # ------------------------------------------------------------------ #

    @property
    def q_value(self) -> float:
        """Mean value from backpropagation."""
        if self.visit_count == 0:
            return 0.0
        return self.total_value / self.visit_count

    @property
    def adjusted_q(self) -> float:
        """Q adjusted for pending virtual losses."""
        n = self.visit_count + self.virtual_loss_count
        if n == 0:
            return 0.0
        return (self.total_value - self.virtual_loss) / n

    @property
    def is_leaf(self) -> bool:
        return not self.children and not self.untried_actions

    @property
    def has_untried(self) -> bool:
        return len(self.untried_actions) > 0

    @property
    def is_fully_expanded(self) -> bool:
        return self.is_expanded and not self.untried_actions

    @property
    def child_count(self) -> int:
        return len(self.children) + len(self.untried_actions)

    # ------------------------------------------------------------------ #
    # Tree operations
    # ------------------------------------------------------------------ #

    def set_legal_actions(
        self,
        actions: list[MCTSAction],
        priors: dict[MCTSAction, float] | None = None,
    ) -> None:
        """
        Populate untried_actions from the simulator's legal action list.
        Called once by the expansion phase on first visit.
        """
        if self.is_expanded:
            return
        if priors:
            # Sort by descending prior so best actions tried first
            self.untried_actions = sorted(
                actions, key=lambda a: priors.get(a, 0.0)
            )
        else:
            self.untried_actions = list(actions)
        self.is_expanded = True
        self.is_terminal = len(actions) == 0 or self.state.is_terminal

    def pop_untried(self) -> MCTSAction:
        """Remove and return one untried action (LIFO — best prior first)."""
        return self.untried_actions.pop()

    def add_child(self, action: MCTSAction, child: MCTSNode) -> None:
        self.children[action] = child

    def best_child(self, key=None) -> MCTSNode | None:
        """Return the child with the highest visit count (or custom key)."""
        if not self.children:
            return None
        return max(self.children.values(), key=key or (lambda c: c.visit_count))

    def apply_virtual_loss(self, amount: float = 3.0) -> None:
        self.virtual_loss += amount
        self.virtual_loss_count += 1

    def undo_virtual_loss(self, amount: float = 3.0) -> None:
        self.virtual_loss = max(0.0, self.virtual_loss - amount)
        self.virtual_loss_count = max(0, self.virtual_loss_count - 1)

    def update(self, value: float) -> None:
        """Update statistics after a simulation."""
        self.visit_count += 1
        self.total_value += value

    # ------------------------------------------------------------------ #
    # Representation
    # ------------------------------------------------------------------ #

    def __repr__(self) -> str:
        return (
            f"MCTSNode(id={self.node_id}, N={self.visit_count}, "
            f"Q={self.q_value:.3f}, depth={self.depth}, "
            f"children={len(self.children)}, terminal={self.is_terminal})"
        )

    def summary(self) -> dict:
        return {
            "node_id": self.node_id,
            "depth": self.depth,
            "player": self.player,
            "visit_count": self.visit_count,
            "q_value": round(self.q_value, 4),
            "prior": round(self.prior, 4),
            "children": len(self.children),
            "untried": len(self.untried_actions),
            "is_terminal": self.is_terminal,
            "action": str(self.action) if self.action else None,
        }
