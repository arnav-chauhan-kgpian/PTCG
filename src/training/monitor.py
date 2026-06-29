"""
Lightweight performance monitor — wraps a section of work with timing
and throughput accounting.  Useful for callbacks that want to emit
"samples/sec" or "rounds/sec" without bespoke timing code.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class PerfMonitor:
    """Single-event throughput timer."""

    label: str = ""
    start_time: float = field(default_factory=time.perf_counter)
    event_count: int = 0
    total_units: int = 0

    def event(self, units: int = 1) -> None:
        self.event_count += 1
        self.total_units += units

    @property
    def elapsed_s(self) -> float:
        return time.perf_counter() - self.start_time

    @property
    def events_per_sec(self) -> float:
        return self.event_count / max(self.elapsed_s, 1e-9)

    @property
    def units_per_sec(self) -> float:
        return self.total_units / max(self.elapsed_s, 1e-9)

    def reset(self) -> None:
        self.start_time = time.perf_counter()
        self.event_count = 0
        self.total_units = 0

    def snapshot(self) -> dict:
        return {
            "label": self.label,
            "elapsed_s": round(self.elapsed_s, 3),
            "events": self.event_count,
            "events_per_sec": round(self.events_per_sec, 2),
            "units": self.total_units,
            "units_per_sec": round(self.units_per_sec, 2),
        }


class Stopwatch:
    """Context-manager timer."""

    def __init__(self) -> None:
        self.elapsed_s: float = 0.0
        self._t0: float = 0.0

    def __enter__(self) -> Stopwatch:
        self._t0 = time.perf_counter()
        return self

    def __exit__(self, *_):
        self.elapsed_s = time.perf_counter() - self._t0
