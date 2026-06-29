"""
Replay buffer for AlphaZero-style supervised training.

Stores ``TrainingSample`` tuples produced by self-play games and supplies
random minibatches to the trainer.  Save/load uses JSON so buffers can be
inspected or transferred between runs without binary tooling.
"""

from __future__ import annotations

import json
import pathlib
import random
from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass

from src.mcts.training_targets import TrainingSample


@dataclass
class ReplayBufferStats:
    appended: int = 0
    sampled: int = 0
    capacity: int = 0
    current_size: int = 0

    def to_dict(self) -> dict:
        return {
            "appended": self.appended,
            "sampled": self.sampled,
            "capacity": self.capacity,
            "current_size": self.current_size,
        }


class ReplayBuffer:
    """
    Fixed-capacity FIFO replay buffer.

    When the buffer fills, the oldest samples are evicted as new ones are
    appended.  Random minibatches can be drawn via ``sample(batch_size)``.
    """

    def __init__(self, capacity: int = 100_000, seed: int | None = None) -> None:
        self.capacity = capacity
        self._store: deque[TrainingSample] = deque(maxlen=capacity)
        self._rng = random.Random(seed)
        self.stats = ReplayBufferStats(capacity=capacity)

    # ------------------------------------------------------------------ #
    # Mutation
    # ------------------------------------------------------------------ #

    def append(self, sample: TrainingSample) -> None:
        self._store.append(sample)
        self.stats.appended += 1
        self.stats.current_size = len(self._store)

    def extend(self, samples: Iterable[TrainingSample]) -> None:
        for s in samples:
            self.append(s)

    def clear(self) -> None:
        self._store.clear()
        self.stats.current_size = 0

    def shuffle(self) -> None:
        items = list(self._store)
        self._rng.shuffle(items)
        self._store = deque(items, maxlen=self.capacity)

    # ------------------------------------------------------------------ #
    # Queries
    # ------------------------------------------------------------------ #

    def __len__(self) -> int:
        return len(self._store)

    def __iter__(self):
        return iter(self._store)

    def __getitem__(self, idx: int) -> TrainingSample:
        return list(self._store)[idx]

    def is_ready(self, min_size: int) -> bool:
        return len(self._store) >= min_size

    # ------------------------------------------------------------------ #
    # Sampling
    # ------------------------------------------------------------------ #

    def sample(self, batch_size: int) -> list[TrainingSample]:
        """Draw *batch_size* samples uniformly with replacement (if needed)."""
        if not self._store:
            return []
        n = len(self._store)
        if batch_size <= n:
            indices = self._rng.sample(range(n), batch_size)
        else:
            indices = [self._rng.randrange(n) for _ in range(batch_size)]
        store_list = list(self._store)
        out = [store_list[i] for i in indices]
        self.stats.sampled += len(out)
        return out

    def sample_features_targets(
        self, batch_size: int
    ) -> tuple[list[tuple[float, ...]], list[tuple[float, ...]], list[float]]:
        """Sample and split into (features, policies, values) lists."""
        batch = self.sample(batch_size)
        features = [s.state_features for s in batch]
        policies = [s.policy_target for s in batch]
        values = [s.value_target for s in batch]
        return features, policies, values

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #

    def save(self, path) -> None:
        path = pathlib.Path(path)
        data = {
            "capacity": self.capacity,
            "samples": [s.to_dict() for s in self._store],
        }
        path.write_text(json.dumps(data), encoding="utf-8")

    @classmethod
    def load(cls, path, seed: int | None = None) -> ReplayBuffer:
        path = pathlib.Path(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        buf = cls(capacity=int(data.get("capacity", 100_000)), seed=seed)
        for sd in data.get("samples", []):
            buf.append(TrainingSample.from_dict(sd))
        return buf

    # ------------------------------------------------------------------ #
    # Diagnostics
    # ------------------------------------------------------------------ #

    def summary(self) -> dict:
        return {
            **self.stats.to_dict(),
            "fullness": round(len(self._store) / self.capacity, 4),
        }
