"""
Logging sinks for the training pipeline.

Supports concurrent CSV, JSONL, console, and TensorBoard sinks behind a
common ``MetricLogger`` facade.  Every record is timestamped (ISO-8601).
"""

from __future__ import annotations

import csv
import datetime
import json
import pathlib
import sys
from dataclasses import dataclass


def _now_iso() -> str:
    # Use timezone-aware UTC (datetime.utcnow() is deprecated in 3.12+)
    return datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


# -------------------------------------------------------------------------
# Individual sinks
# -------------------------------------------------------------------------

class CSVSink:
    def __init__(self, path) -> None:
        self.path = pathlib.Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._headers: list[str] | None = None
        if self.path.exists() and self.path.stat().st_size > 0:
            with self.path.open() as fh:
                first = fh.readline().strip()
            self._headers = first.split(",") if first else None

    def log(self, record: dict) -> None:
        # Stable key order: timestamp + sorted other keys
        keys = ["timestamp"] + sorted(k for k in record if k != "timestamp")
        if self._headers is None:
            self._headers = keys
            with self.path.open("w", newline="", encoding="utf-8") as fh:
                writer = csv.writer(fh)
                writer.writerow(self._headers)
        with self.path.open("a", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            row = [record.get(k, "") for k in self._headers]
            writer.writerow(row)


class JSONLSink:
    def __init__(self, path) -> None:
        self.path = pathlib.Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, record: dict) -> None:
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, default=str) + "\n")


class ConsoleSink:
    def __init__(self, stream=None) -> None:
        self.stream = stream or sys.stdout

    def log(self, record: dict) -> None:
        keys = sorted(k for k in record if k != "timestamp")
        msg = " ".join(f"{k}={record[k]}" for k in keys)
        print(f"[{record.get('timestamp', '')}] {msg}", file=self.stream)


class TensorBoardSink:
    """Best-effort TensorBoard sink — silently no-op if SummaryWriter missing."""

    def __init__(self, log_dir) -> None:
        self.writer = None
        try:
            from torch.utils.tensorboard import SummaryWriter
            self.writer = SummaryWriter(log_dir=str(log_dir))
        except Exception:
            self.writer = None
        self._step = 0

    def log(self, record: dict) -> None:
        if self.writer is None:
            return
        step = int(record.get("step", self._step))
        for key, value in record.items():
            if key in ("timestamp", "step"):
                continue
            try:
                self.writer.add_scalar(key, float(value), step)
            except (TypeError, ValueError):
                pass
        self._step = step + 1

    def close(self) -> None:
        if self.writer is not None:
            try:
                self.writer.flush()
                self.writer.close()
            except Exception:
                pass


# -------------------------------------------------------------------------
# Facade
# -------------------------------------------------------------------------

@dataclass
class MetricLogger:
    """
    Facade over multiple sinks. ``log(category, record)`` fans out to all
    enabled sinks with a stable timestamp prepended.
    """

    log_dir: str = "logs"
    csv: bool = True
    jsonl: bool = True
    console: bool = True
    tensorboard: bool = False
    log_every: int = 1

    def __post_init__(self) -> None:
        root = pathlib.Path(self.log_dir)
        root.mkdir(parents=True, exist_ok=True)
        self._sinks: list = []
        if self.csv:
            self._sinks.append(("csv", CSVSink(root / "metrics.csv")))
        if self.jsonl:
            self._sinks.append(("jsonl", JSONLSink(root / "metrics.jsonl")))
        if self.console:
            self._sinks.append(("console", ConsoleSink()))
        if self.tensorboard:
            self._sinks.append(("tb", TensorBoardSink(root / "tb")))
        self._count = 0

    def log(self, category: str, record: dict, force: bool = False) -> None:
        self._count += 1
        if not force and self._count % max(1, self.log_every) != 0:
            return
        payload = {"timestamp": _now_iso(), "category": category, **record}
        for _, sink in self._sinks:
            try:
                sink.log(payload)
            except Exception:
                pass

    def close(self) -> None:
        for _, sink in self._sinks:
            if hasattr(sink, "close"):
                try:
                    sink.close()
                except Exception:
                    pass
