"""
Transposition table — reuse previously computed nodes for identical states.

Two different paths through the game tree can reach the same board position.
The transposition table maps state fingerprint → MCTSNode so the second
arrival re-uses the first node's statistics instead of starting fresh.

Uses Phase 7 ``state_fingerprint`` for keys.

Eviction policy: LRU via ``collections.OrderedDict``.  When the table
exceeds ``max_size``, the least-recently-used entry is removed.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.game_state.state import GameState
    from src.mcts.node import MCTSNode


@dataclass
class TranspositionStats:
    hits: int = 0
    misses: int = 0
    inserts: int = 0
    evictions: int = 0

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total else 0.0

    def __repr__(self) -> str:
        return (
            f"TranspositionStats(hits={self.hits}, misses={self.misses}, "
            f"hit_rate={self.hit_rate:.2%}, inserts={self.inserts}, "
            f"evictions={self.evictions})"
        )


class TranspositionTable:
    """
    LRU transposition table for MCTSNode reuse.

    Keys are state fingerprints (SHA-256 hex strings from hashing.py).
    Nodes are stored by reference — modifying a node outside the table
    is visible through the table (by design: shared statistics).
    """

    def __init__(self, max_size: int = 100_000) -> None:
        self.max_size = max_size
        self._store: OrderedDict[str, MCTSNode] = OrderedDict()
        self.stats = TranspositionStats()

    # ------------------------------------------------------------------ #
    # Core operations
    # ------------------------------------------------------------------ #

    def lookup(self, fingerprint: str) -> MCTSNode | None:
        """Return the node for *fingerprint*, or None (cache miss)."""
        node = self._store.get(fingerprint)
        if node is not None:
            # Move to end (most recently used)
            self._store.move_to_end(fingerprint)
            self.stats.hits += 1
        else:
            self.stats.misses += 1
        return node

    def lookup_by_state(self, state: GameState) -> MCTSNode | None:
        from src.game_state.hashing import state_fingerprint
        return self.lookup(state_fingerprint(state))

    def insert(self, node: MCTSNode) -> None:
        """Insert *node* keyed by its state_hash."""
        fp = node.state_hash
        if fp in self._store:
            self._store.move_to_end(fp)
            return

        self._store[fp] = node
        self.stats.inserts += 1

        if len(self._store) > self.max_size:
            self._store.popitem(last=False)  # evict LRU
            self.stats.evictions += 1

    def replace(self, node: MCTSNode) -> None:
        """Unconditionally replace any existing entry for node's hash."""
        fp = node.state_hash
        self._store[fp] = node
        self._store.move_to_end(fp)
        self.stats.inserts += 1
        if len(self._store) > self.max_size:
            self._store.popitem(last=False)
            self.stats.evictions += 1

    def __contains__(self, fingerprint: str) -> bool:
        return fingerprint in self._store

    def __len__(self) -> int:
        return len(self._store)

    # ------------------------------------------------------------------ #
    # Bulk operations
    # ------------------------------------------------------------------ #

    def clear(self) -> None:
        self._store.clear()
        self.stats = TranspositionStats()

    def retain_subtree(self, root_fingerprint: str) -> int:
        """
        Remove all entries whose fingerprint is not reachable from root.

        This is a heuristic: we keep only entries that share the root's
        hash prefix (first 8 chars) — a conservative approximation of
        "same game branch".  A full reachability check would require
        walking the tree.

        Returns the number of entries retained.
        """
        prefix = root_fingerprint[:8]
        to_delete = [
            k for k in self._store if not k.startswith(prefix)
        ]
        for k in to_delete:
            del self._store[k]
        return len(self._store)

    # ------------------------------------------------------------------ #
    # Diagnostics
    # ------------------------------------------------------------------ #

    def summary(self) -> dict:
        return {
            "size": len(self._store),
            "max_size": self.max_size,
            "utilisation": len(self._store) / self.max_size,
            **vars(self.stats),
            "hit_rate": self.stats.hit_rate,
        }
