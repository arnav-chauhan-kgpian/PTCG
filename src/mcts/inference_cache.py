"""
LRU inference cache — avoid redundant neural forward passes.

Caches ``(policy_logits, value)`` keyed by a state's fingerprint.  The
cache is process-local and not persisted: it lives for the lifetime of a
single MCTSSearch instance (or self-play game).

Designed for use inside ``NeuralEvaluator`` and ``NeuralPriorPolicy`` so a
single state encountered through different paths only triggers one
forward pass.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.game_state.state import GameState


@dataclass
class InferenceCacheStats:
    hits: int = 0
    misses: int = 0
    inserts: int = 0
    evictions: int = 0

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total else 0.0

    def to_dict(self) -> dict:
        return {
            "hits": self.hits,
            "misses": self.misses,
            "inserts": self.inserts,
            "evictions": self.evictions,
            "hit_rate": round(self.hit_rate, 4),
        }


class InferenceCache:
    """
    LRU cache mapping state fingerprint → (policy_logits, value).

    Reuses Phase 7 ``state_fingerprint`` for keys so any cache hit is
    structurally exact.
    """

    def __init__(self, max_size: int = 50_000) -> None:
        self.max_size = max_size
        self._store: OrderedDict[str, tuple[list[float], float]] = OrderedDict()
        self.stats = InferenceCacheStats()

    # ------------------------------------------------------------------ #
    # Key helper
    # ------------------------------------------------------------------ #

    @staticmethod
    def key_for(state: GameState) -> str:
        from src.game_state.hashing import state_fingerprint
        return state_fingerprint(state)

    # ------------------------------------------------------------------ #
    # Core operations
    # ------------------------------------------------------------------ #

    def get(self, key: str) -> tuple[list[float], float] | None:
        entry = self._store.get(key)
        if entry is None:
            self.stats.misses += 1
            return None
        self._store.move_to_end(key)
        self.stats.hits += 1
        return entry

    def get_by_state(self, state: GameState) -> tuple[list[float], float] | None:
        return self.get(self.key_for(state))

    def put(self, key: str, policy: list[float], value: float) -> None:
        if key in self._store:
            self._store.move_to_end(key)
            self._store[key] = (policy, value)
            return
        self._store[key] = (policy, value)
        self.stats.inserts += 1
        if len(self._store) > self.max_size:
            self._store.popitem(last=False)
            self.stats.evictions += 1

    def put_for_state(
        self, state: GameState, policy: list[float], value: float
    ) -> None:
        self.put(self.key_for(state), policy, value)

    def __contains__(self, key: str) -> bool:
        return key in self._store

    def __len__(self) -> int:
        return len(self._store)

    def clear(self) -> None:
        self._store.clear()
        self.stats = InferenceCacheStats()

    # ------------------------------------------------------------------ #
    # Diagnostics
    # ------------------------------------------------------------------ #

    def summary(self) -> dict:
        return {
            "size": len(self._store),
            "max_size": self.max_size,
            "utilisation": round(len(self._store) / self.max_size, 4),
            **self.stats.to_dict(),
        }
