"""
Live training metrics.

Accumulated by the trainer across steps and rounds; consumed by loggers
and callbacks.  All counters are plain Python so the module works without
PyTorch.
"""

from __future__ import annotations

import collections
import time
from dataclasses import dataclass, field


@dataclass
class RollingMean:
    """O(1) rolling mean over the last ``window`` samples."""
    window: int = 100
    _values: collections.deque = field(default_factory=lambda: collections.deque(maxlen=100))

    def __post_init__(self):
        if self._values.maxlen != self.window:
            self._values = collections.deque(maxlen=self.window)

    def push(self, value: float) -> None:
        self._values.append(value)

    @property
    def value(self) -> float:
        return sum(self._values) / len(self._values) if self._values else 0.0

    def __len__(self) -> int:
        return len(self._values)


@dataclass
class TrainingMetrics:
    """Accumulated training metrics for one run."""

    # Counters
    rounds: int = 0
    training_steps: int = 0
    games_played: int = 0
    moves_generated: int = 0
    samples_seen: int = 0
    promotions: int = 0

    # Last-step values
    last_policy_loss: float = 0.0
    last_value_loss: float = 0.0
    last_total_loss: float = 0.0
    last_learning_rate: float = 0.0
    last_win_rate: float = 0.0

    # Rolling averages
    policy_loss: RollingMean = field(default_factory=RollingMean)
    value_loss: RollingMean = field(default_factory=RollingMean)
    total_loss: RollingMean = field(default_factory=RollingMean)
    win_rate: RollingMean = field(default_factory=RollingMean)
    game_length: RollingMean = field(default_factory=RollingMean)
    branching_factor: RollingMean = field(default_factory=RollingMean)
    search_depth: RollingMean = field(default_factory=RollingMean)
    nodes_per_sec: RollingMean = field(default_factory=RollingMean)
    cache_hit_rate: RollingMean = field(default_factory=RollingMean)
    samples_per_sec: RollingMean = field(default_factory=RollingMean)

    # State
    replay_size: int = 0
    best_loss: float = float("inf")
    best_win_rate: float = 0.0
    start_time: float = field(default_factory=time.perf_counter)
    promotion_history: list[dict] = field(default_factory=list)

    # ------------------------------------------------------------------ #
    # Updates
    # ------------------------------------------------------------------ #

    def record_train_step(
        self,
        policy_loss: float, value_loss: float, total_loss: float,
        learning_rate: float,
    ) -> None:
        self.training_steps += 1
        self.last_policy_loss = policy_loss
        self.last_value_loss = value_loss
        self.last_total_loss = total_loss
        self.last_learning_rate = learning_rate
        self.policy_loss.push(policy_loss)
        self.value_loss.push(value_loss)
        self.total_loss.push(total_loss)
        if total_loss < self.best_loss:
            self.best_loss = total_loss

    def record_selfplay_game(
        self,
        moves: int,
        nodes_per_sec: float = 0.0,
        branching: float = 0.0,
        depth: float = 0.0,
        cache_hit_rate: float = 0.0,
    ) -> None:
        self.games_played += 1
        self.moves_generated += moves
        self.game_length.push(moves)
        if nodes_per_sec > 0:
            self.nodes_per_sec.push(nodes_per_sec)
        if branching > 0:
            self.branching_factor.push(branching)
        if depth > 0:
            self.search_depth.push(depth)
        if cache_hit_rate > 0:
            self.cache_hit_rate.push(cache_hit_rate)

    def record_arena(self, win_rate: float) -> None:
        self.last_win_rate = win_rate
        self.win_rate.push(win_rate)
        if win_rate > self.best_win_rate:
            self.best_win_rate = win_rate

    def record_promotion(self, info: dict) -> None:
        self.promotions += 1
        self.promotion_history.append(info)

    def record_round(self) -> None:
        self.rounds += 1

    @property
    def elapsed_s(self) -> float:
        return time.perf_counter() - self.start_time

    @property
    def throughput_samples_per_sec(self) -> float:
        return self.samples_seen / max(self.elapsed_s, 1e-9)

    # ------------------------------------------------------------------ #
    # Snapshot
    # ------------------------------------------------------------------ #

    def snapshot(self) -> dict:
        return {
            "rounds": self.rounds,
            "training_steps": self.training_steps,
            "games_played": self.games_played,
            "moves_generated": self.moves_generated,
            "samples_seen": self.samples_seen,
            "promotions": self.promotions,
            "last_policy_loss": round(self.last_policy_loss, 6),
            "last_value_loss": round(self.last_value_loss, 6),
            "last_total_loss": round(self.last_total_loss, 6),
            "last_learning_rate": self.last_learning_rate,
            "last_win_rate": round(self.last_win_rate, 4),
            "avg_policy_loss": round(self.policy_loss.value, 6),
            "avg_value_loss": round(self.value_loss.value, 6),
            "avg_total_loss": round(self.total_loss.value, 6),
            "avg_win_rate": round(self.win_rate.value, 4),
            "avg_game_length": round(self.game_length.value, 2),
            "avg_branching": round(self.branching_factor.value, 2),
            "avg_search_depth": round(self.search_depth.value, 2),
            "avg_nodes_per_sec": round(self.nodes_per_sec.value, 1),
            "avg_cache_hit_rate": round(self.cache_hit_rate.value, 4),
            "throughput_samples_per_sec": round(self.throughput_samples_per_sec, 1),
            "best_loss": round(self.best_loss, 6) if self.best_loss != float("inf") else None,
            "best_win_rate": round(self.best_win_rate, 4),
            "elapsed_s": round(self.elapsed_s, 2),
            "replay_size": self.replay_size,
            "promotion_count": len(self.promotion_history),
        }
