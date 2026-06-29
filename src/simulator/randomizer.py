"""
Centralized seeded randomness for the simulator.

A single ``Randomizer`` instance owns the RNG used by setup, shuffles,
coin flips, and draw resolution.  Reuses Python's ``random.Random`` for
determinism with a given seed.
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from typing import TypeVar

T = TypeVar("T")


class Randomizer:
    """Thin RNG wrapper with explicit, named operations for auditability."""

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)
        self._coin_flips: list[bool] = []   # history for replay/debugging
        self._shuffles: int = 0
        self.seed = seed

    def coin_flip(self) -> bool:
        """Return True for heads, False for tails."""
        outcome = self._rng.random() < 0.5
        self._coin_flips.append(outcome)
        return outcome

    def coin_flips(self, n: int) -> list[bool]:
        return [self.coin_flip() for _ in range(n)]

    def shuffle(self, items: list[T]) -> list[T]:
        """Return a shuffled copy of *items*."""
        shuffled = list(items)
        self._rng.shuffle(shuffled)
        self._shuffles += 1
        return shuffled

    def choice(self, items: Sequence[T]) -> T:
        return self._rng.choice(list(items))

    def random(self) -> float:
        return self._rng.random()

    def randint(self, lo: int, hi: int) -> int:
        return self._rng.randint(lo, hi)

    @property
    def coin_flip_history(self) -> tuple[bool, ...]:
        return tuple(self._coin_flips)

    @property
    def shuffle_count(self) -> int:
        return self._shuffles
