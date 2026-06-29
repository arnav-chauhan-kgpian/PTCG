"""
MCTSTree — explicit search tree container.

Manages the set of all MCTSNodes created during a search, tracks depth and
breadth statistics, and provides the principal variation extraction.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.mcts.node import MCTSAction, MCTSNode

if TYPE_CHECKING:
    from src.game_state.state import GameState


class MCTSTree:
    """
    Container for an MCTS search tree rooted at a given GameState.

    Responsibilities
    ----------------
    - Hold the root node
    - Count total nodes for memory management
    - Extract principal variation (best-move sequence)
    - Provide subtree pruning for tree reuse
    """

    def __init__(self, root_state: GameState) -> None:
        self.root = MCTSNode(state=root_state)
        self._node_count: int = 1
        self._max_depth: int = 0

    # ------------------------------------------------------------------ #
    # Node accounting
    # ------------------------------------------------------------------ #

    @property
    def node_count(self) -> int:
        return self._node_count

    @property
    def max_depth(self) -> int:
        return self._max_depth

    def register_node(self, node: MCTSNode) -> None:
        """Called each time a new MCTSNode is created during search."""
        self._node_count += 1
        if node.depth > self._max_depth:
            self._max_depth = node.depth

    # ------------------------------------------------------------------ #
    # Principal variation
    # ------------------------------------------------------------------ #

    def principal_variation(self, max_depth: int = 10) -> list[MCTSAction]:
        """
        Extract the principal variation (most-visited path from root).

        At each level the child with the highest visit count is followed.
        """
        pv: list[MCTSAction] = []
        node = self.root
        depth = 0

        while depth < max_depth:
            best = node.best_child(key=lambda c: c.visit_count)
            if best is None or best.action is None:
                break
            pv.append(best.action)
            node = best
            depth += 1

        return pv

    # ------------------------------------------------------------------ #
    # Action statistics
    # ------------------------------------------------------------------ #

    def root_action_stats(self) -> dict[MCTSAction, dict]:
        """Return visit counts and Q-values for all root children."""
        return {
            action: {
                "visit_count": child.visit_count,
                "q_value": round(child.q_value, 4),
                "prior": round(child.prior, 4),
            }
            for action, child in self.root.children.items()
        }

    def best_action(self, key: str = "visit_count") -> MCTSAction | None:
        """
        Return the action that should be played.

        key="visit_count"  → robust choice (most visited = most confident)
        key="q_value"      → greedy choice (highest mean value)
        """
        if not self.root.children:
            return None

        if key == "visit_count":
            return max(
                self.root.children,
                key=lambda a: self.root.children[a].visit_count,
            )
        elif key == "q_value":
            return max(
                self.root.children,
                key=lambda a: self.root.children[a].q_value,
            )
        else:
            raise ValueError(f"Unknown key: {key!r}")

    def action_ranking(self, normalize: bool = True) -> list[tuple[MCTSAction, float]]:
        """
        Return (action, score) pairs sorted by descending visit count.

        If normalize=True, scores are fractions of total root visits.
        """
        total = max(self.root.visit_count, 1)
        items = [
            (a, c.visit_count / total if normalize else float(c.visit_count))
            for a, c in self.root.children.items()
        ]
        return sorted(items, key=lambda x: x[1], reverse=True)

    # ------------------------------------------------------------------ #
    # Tree reuse
    # ------------------------------------------------------------------ #

    def advance_root(self, action: MCTSAction) -> bool:
        """
        Set the tree root to the child reached by *action*.

        Used for tree reuse: the subtree under the played action is
        retained for the next move.  Returns True if the subtree was found.
        """
        child = self.root.children.get(action)
        if child is None:
            return False
        child.parent = None  # detach from old root
        self.root = child
        # Note: _node_count is now an overcount — acceptable for heuristics
        return True

    # ------------------------------------------------------------------ #
    # Diagnostics
    # ------------------------------------------------------------------ #

    def summary(self) -> dict:
        return {
            "root_visits": self.root.visit_count,
            "root_q": round(self.root.q_value, 4),
            "node_count": self._node_count,
            "max_depth": self._max_depth,
            "root_children": len(self.root.children),
            "root_untried": len(self.root.untried_actions),
        }

    def depth_histogram(self, max_depth: int = 20) -> dict[int, int]:
        """Count nodes at each depth via BFS."""
        from collections import deque
        counts: dict[int, int] = {}
        q: deque[MCTSNode] = deque([self.root])
        while q:
            node = q.popleft()
            counts[node.depth] = counts.get(node.depth, 0) + 1
            if node.depth < max_depth:
                q.extend(node.children.values())
        return dict(sorted(counts.items()))
