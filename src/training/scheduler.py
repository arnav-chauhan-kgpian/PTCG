"""
Outer-loop round scheduler.

Decides whether the pipeline should run another *round* (self-play +
training + eval).  Wraps the existing ``EarlyStopping`` plus simple round
caps; the trainer's per-batch loop has its own ``mcts.SearchScheduler``.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class RoundScheduler:
    """
    Tracks whether the outer training loop should continue.

    Stops when ANY of:
      • ``max_rounds`` reached
      • ``max_wall_clock_s`` elapsed
      • ``early_stop_triggered`` set externally (e.g. by EarlyStopping)
    """

    max_rounds: int = 100
    max_wall_clock_s: float | None = None
    started_at: float = field(default_factory=time.perf_counter)
    rounds_done: int = 0
    early_stop_triggered: bool = False
    stop_reason: str = ""

    def reset(self) -> None:
        self.started_at = time.perf_counter()
        self.rounds_done = 0
        self.early_stop_triggered = False
        self.stop_reason = ""

    def should_continue(self) -> bool:
        if self.early_stop_triggered:
            return False
        if self.rounds_done >= self.max_rounds:
            self.stop_reason = f"max_rounds={self.max_rounds}"
            return False
        if (
            self.max_wall_clock_s is not None
            and (time.perf_counter() - self.started_at) >= self.max_wall_clock_s
        ):
            self.stop_reason = f"max_wall_clock_s={self.max_wall_clock_s}"
            return False
        return True

    def tick(self) -> None:
        self.rounds_done += 1

    def trigger_early_stop(self, reason: str) -> None:
        self.early_stop_triggered = True
        self.stop_reason = reason

    @property
    def elapsed_s(self) -> float:
        return time.perf_counter() - self.started_at

    def summary(self) -> dict:
        return {
            "rounds_done": self.rounds_done,
            "max_rounds": self.max_rounds,
            "elapsed_s": round(self.elapsed_s, 2),
            "early_stop_triggered": self.early_stop_triggered,
            "stop_reason": self.stop_reason,
        }
