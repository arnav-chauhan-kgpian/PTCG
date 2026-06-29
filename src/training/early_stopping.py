"""
Early stopping for the training pipeline.

Tracks improvement of a monitored metric, plus optional wall-clock and
step / epoch caps.  Holds zero PyTorch-specific state.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class EarlyStopping:
    """Composite stop policy."""

    patience: int = 10
    min_improvement: float = 1e-4
    mode: str = "min"                # "min" → smaller is better; "max" → larger
    max_wall_clock_s: float | None = None
    max_epochs: int | None = None
    max_training_steps: int | None = None

    # Runtime state
    best: float = field(default=float("inf"))
    no_improve_count: int = 0
    started_at: float = field(default_factory=time.perf_counter)
    triggered: bool = False
    trigger_reason: str = ""

    def __post_init__(self) -> None:
        if self.mode == "max":
            self.best = float("-inf")

    def reset(self) -> None:
        self.best = float("inf") if self.mode == "min" else float("-inf")
        self.no_improve_count = 0
        self.started_at = time.perf_counter()
        self.triggered = False
        self.trigger_reason = ""

    # ------------------------------------------------------------------ #
    # Update
    # ------------------------------------------------------------------ #

    def update(
        self,
        metric: float,
        *,
        epoch: int | None = None,
        step: int | None = None,
    ) -> bool:
        """Update with the latest metric. Return True if stop is triggered."""
        improved = self._improved(metric)
        if improved:
            self.best = metric
            self.no_improve_count = 0
        else:
            self.no_improve_count += 1

        if self.no_improve_count >= self.patience:
            self._trigger(f"patience={self.patience} exhausted")
            return True

        if self.max_wall_clock_s is not None:
            elapsed = time.perf_counter() - self.started_at
            if elapsed >= self.max_wall_clock_s:
                self._trigger(f"max_wall_clock_s={self.max_wall_clock_s} reached")
                return True

        if self.max_epochs is not None and epoch is not None and epoch >= self.max_epochs:
            self._trigger(f"max_epochs={self.max_epochs} reached")
            return True

        if (
            self.max_training_steps is not None
            and step is not None
            and step >= self.max_training_steps
        ):
            self._trigger(f"max_training_steps={self.max_training_steps} reached")
            return True

        return False

    def _improved(self, metric: float) -> bool:
        if self.mode == "min":
            return metric < self.best - self.min_improvement
        return metric > self.best + self.min_improvement

    def _trigger(self, reason: str) -> None:
        self.triggered = True
        self.trigger_reason = reason

    @classmethod
    def from_config(cls, cfg) -> EarlyStopping:
        return cls(
            patience=cfg.patience,
            min_improvement=cfg.min_improvement,
            max_wall_clock_s=cfg.max_wall_clock_s,
            max_epochs=cfg.max_epochs,
            max_training_steps=cfg.max_training_steps,
        )

    def summary(self) -> dict:
        return {
            "patience": self.patience,
            "no_improve_count": self.no_improve_count,
            "best": self.best if self.best not in (float("inf"), float("-inf")) else None,
            "triggered": self.triggered,
            "reason": self.trigger_reason,
            "elapsed_s": round(time.perf_counter() - self.started_at, 2),
        }
