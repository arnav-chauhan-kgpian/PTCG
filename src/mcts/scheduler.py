"""
SearchScheduler — controls when the MCTS loop terminates.

Supports both iteration-count and wall-clock time budget stopping criteria.
Either or both can be active simultaneously.
"""

from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass
class SearchScheduler:
    """
    Tracks MCTS loop progress and decides when to stop.

    Usage::

        sched = SearchScheduler(max_iterations=800, time_budget_s=2.0)
        sched.start()
        while sched.should_continue():
            # ... one MCTS iteration ...
            sched.tick()
        result = sched.summary()
    """

    max_iterations: int = 800
    time_budget_s: float = 2.0

    # ── Runtime state ────────────────────────────────────────────────
    _start_time: float = 0.0
    _iterations: int = 0
    _running: bool = False

    def start(self) -> SearchScheduler:
        self._start_time = time.perf_counter()
        self._iterations = 0
        self._running = True
        return self

    def tick(self) -> None:
        self._iterations += 1

    def should_continue(self) -> bool:
        if not self._running:
            return False
        if self._iterations >= self.max_iterations:
            return False
        elapsed = time.perf_counter() - self._start_time
        if elapsed >= self.time_budget_s:
            return False
        return True

    def stop(self) -> None:
        self._running = False

    @property
    def iterations_done(self) -> int:
        return self._iterations

    @property
    def elapsed_s(self) -> float:
        if not self._start_time:
            return 0.0
        return time.perf_counter() - self._start_time

    @property
    def iterations_per_second(self) -> float:
        elapsed = self.elapsed_s
        if elapsed <= 0:
            return 0.0
        return self._iterations / elapsed

    def summary(self) -> dict:
        return {
            "iterations": self._iterations,
            "elapsed_s": round(self.elapsed_s, 4),
            "iterations_per_second": round(self.iterations_per_second, 1),
            "stopped_by": self._stopped_by(),
        }

    def _stopped_by(self) -> str:
        if self._iterations >= self.max_iterations:
            return "iterations"
        if self.elapsed_s >= self.time_budget_s:
            return "time_budget"
        return "external"

    @classmethod
    def from_config(cls, config) -> SearchScheduler:
        return cls(
            max_iterations=config.iterations,
            time_budget_s=config.time_budget_s,
        )
