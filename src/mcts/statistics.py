"""
Search statistics — collected throughout one MCTS search call.

Tracks node creation, evaluations, rollouts, backpropagation steps,
and timing breakdowns.  Returned as part of SearchResult.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class SearchStatistics:
    """
    Live statistics accumulated during a single MCTS search.

    All counters increment monotonically; call ``snapshot()`` to read
    a frozen copy at any point.
    """

    # ── Counts ────────────────────────────────────────────────────────
    iterations: int = 0
    nodes_created: int = 0
    nodes_expanded: int = 0         # nodes that had legal actions computed
    evaluations: int = 0            # calls to evaluator.evaluate()
    rollout_steps: int = 0          # total steps across all rollouts
    backprop_steps: int = 0         # individual node updates
    transposition_hits: int = 0
    transposition_misses: int = 0

    # ── Timing ─────────────────────────────────────────────────────────
    selection_time_s: float = 0.0
    expansion_time_s: float = 0.0
    evaluation_time_s: float = 0.0
    backprop_time_s: float = 0.0
    total_time_s: float = 0.0

    # ── Value tracking ─────────────────────────────────────────────────
    _value_sum: float = field(default=0.0, repr=False)
    _value_min: float = field(default=float("inf"), repr=False)
    _value_max: float = field(default=float("-inf"), repr=False)

    def record_value(self, value: float) -> None:
        self._value_sum += value
        if value < self._value_min:
            self._value_min = value
        if value > self._value_max:
            self._value_max = value

    @property
    def mean_value(self) -> float:
        return self._value_sum / self.evaluations if self.evaluations else 0.0

    @property
    def min_value(self) -> float:
        return self._value_min if self._value_min != float("inf") else 0.0

    @property
    def max_value(self) -> float:
        return self._value_max if self._value_max != float("-inf") else 0.0

    # ── Derived ────────────────────────────────────────────────────────

    @property
    def iterations_per_second(self) -> float:
        return self.iterations / self.total_time_s if self.total_time_s else 0.0

    @property
    def transposition_hit_rate(self) -> float:
        total = self.transposition_hits + self.transposition_misses
        return self.transposition_hits / total if total else 0.0

    # ── Output ─────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "iterations": self.iterations,
            "nodes_created": self.nodes_created,
            "nodes_expanded": self.nodes_expanded,
            "evaluations": self.evaluations,
            "rollout_steps": self.rollout_steps,
            "backprop_steps": self.backprop_steps,
            "transposition_hits": self.transposition_hits,
            "transposition_misses": self.transposition_misses,
            "transposition_hit_rate": round(self.transposition_hit_rate, 4),
            "mean_value": round(self.mean_value, 4),
            "min_value": round(self.min_value, 4),
            "max_value": round(self.max_value, 4),
            "total_time_s": round(self.total_time_s, 4),
            "iterations_per_second": round(self.iterations_per_second, 1),
            "selection_time_s": round(self.selection_time_s, 4),
            "expansion_time_s": round(self.expansion_time_s, 4),
            "evaluation_time_s": round(self.evaluation_time_s, 4),
            "backprop_time_s": round(self.backprop_time_s, 4),
        }

    def __repr__(self) -> str:
        return (
            f"SearchStatistics(iter={self.iterations}, "
            f"nodes={self.nodes_created}, "
            f"evals={self.evaluations}, "
            f"t={self.total_time_s:.3f}s, "
            f"ips={self.iterations_per_second:.0f})"
        )


class _Timer:
    """Context manager for timing a code block."""

    def __init__(self, attr: str, stats: SearchStatistics) -> None:
        self._attr = attr
        self._stats = stats
        self._t0: float = 0.0

    def __enter__(self) -> _Timer:
        self._t0 = time.perf_counter()
        return self

    def __exit__(self, *_) -> None:
        elapsed = time.perf_counter() - self._t0
        current = getattr(self._stats, self._attr)
        setattr(self._stats, self._attr, current + elapsed)


def timer(attr: str, stats: SearchStatistics) -> _Timer:
    """Convenience: ``with timer("selection_time_s", stats): ...``"""
    return _Timer(attr, stats)
