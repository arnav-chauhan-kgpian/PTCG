"""
Experiment lifecycle management.

An *experiment* is a labelled directory containing everything needed to
reproduce a training run: config snapshot, git hash, seed, hardware info,
checkpoint lineage, metrics history, best-checkpoint pointer.

This module is filesystem-only — no compute, no torch dependency.
"""

from __future__ import annotations

import datetime
import json
import os
import pathlib
import platform
import subprocess
import sys
from dataclasses import asdict, dataclass, field


def _git_hash() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=os.getcwd(),
            stderr=subprocess.DEVNULL, timeout=2,
        ).decode("utf-8").strip()
    except Exception:
        return None


def _now_iso() -> str:
    return datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _hardware_info() -> dict:
    info = {
        "platform": platform.system(),
        "platform_release": platform.release(),
        "machine": platform.machine(),
        "python": sys.version.split()[0],
    }
    try:
        import torch
        info["torch"] = torch.__version__
        info["cuda_available"] = torch.cuda.is_available()
        if torch.cuda.is_available():
            info["cuda_device"] = torch.cuda.get_device_name(0)
    except Exception:
        info["torch"] = None
    return info


# -------------------------------------------------------------------------
# Manifest dataclass
# -------------------------------------------------------------------------

@dataclass
class ExperimentManifest:
    """Self-describing record of one experiment run."""

    name: str
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)
    git_hash: str | None = field(default_factory=_git_hash)
    seed: int | None = None
    dataset_version: str | None = None
    config_snapshot: dict = field(default_factory=dict)
    hardware: dict = field(default_factory=_hardware_info)
    checkpoint_lineage: list[str] = field(default_factory=list)
    best_checkpoint: str | None = None
    metrics_history: list[dict] = field(default_factory=list)
    promotion_history: list[dict] = field(default_factory=list)
    training_duration_s: float = 0.0
    status: str = "running"          # "running" | "completed" | "failed" | "stopped"
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# -------------------------------------------------------------------------
# Manager
# -------------------------------------------------------------------------

class ExperimentManager:
    """
    Owns one experiment directory.

    Layout::

        <experiment_dir>/<name>/
            manifest.json
            metrics/                 ← MetricLogger sinks
            checkpoints/             ← CheckpointManager
            pipeline_checkpoints/    ← PipelineCheckpointStore
    """

    def __init__(
        self,
        root,
        name: str,
        config_snapshot: dict | None = None,
        seed: int | None = None,
        dataset_version: str | None = None,
    ) -> None:
        self.root = pathlib.Path(root) / name
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "checkpoints").mkdir(exist_ok=True)
        (self.root / "metrics").mkdir(exist_ok=True)
        (self.root / "pipeline_checkpoints").mkdir(exist_ok=True)

        self.manifest_path = self.root / "manifest.json"
        if self.manifest_path.exists():
            data = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            self.manifest = ExperimentManifest(**{
                k: v for k, v in data.items()
                if k in ExperimentManifest("__placeholder__").to_dict()
            })
            if config_snapshot:
                self.manifest.config_snapshot = config_snapshot
        else:
            self.manifest = ExperimentManifest(
                name=name,
                seed=seed,
                dataset_version=dataset_version,
                config_snapshot=config_snapshot or {},
            )
        self.save()

    # ------------------------------------------------------------------ #
    # Recording
    # ------------------------------------------------------------------ #

    def record_checkpoint(self, name: str, is_best: bool = False) -> None:
        if name not in self.manifest.checkpoint_lineage:
            self.manifest.checkpoint_lineage.append(name)
        if is_best:
            self.manifest.best_checkpoint = name
        self._touch()

    def record_metrics(self, snapshot: dict) -> None:
        self.manifest.metrics_history.append({"timestamp": _now_iso(), **snapshot})
        self._touch()

    def record_promotion(self, info: dict) -> None:
        self.manifest.promotion_history.append({"timestamp": _now_iso(), **info})
        self._touch()

    def set_training_duration(self, seconds: float) -> None:
        self.manifest.training_duration_s = float(seconds)
        self._touch()

    def set_status(self, status: str, notes: str = "") -> None:
        self.manifest.status = status
        if notes:
            self.manifest.notes = notes
        self._touch()

    def _touch(self) -> None:
        self.manifest.updated_at = _now_iso()
        self.save()

    # ------------------------------------------------------------------ #
    # I/O
    # ------------------------------------------------------------------ #

    def save(self) -> None:
        self.manifest_path.write_text(
            json.dumps(self.manifest.to_dict(), indent=2),
            encoding="utf-8",
        )

    @property
    def checkpoints_dir(self) -> pathlib.Path:
        return self.root / "checkpoints"

    @property
    def metrics_dir(self) -> pathlib.Path:
        return self.root / "metrics"

    @property
    def pipeline_checkpoints_dir(self) -> pathlib.Path:
        return self.root / "pipeline_checkpoints"

    def summary(self) -> dict:
        return {
            "name": self.manifest.name,
            "status": self.manifest.status,
            "created_at": self.manifest.created_at,
            "updated_at": self.manifest.updated_at,
            "checkpoints": len(self.manifest.checkpoint_lineage),
            "best": self.manifest.best_checkpoint,
            "promotions": len(self.manifest.promotion_history),
            "training_duration_s": round(self.manifest.training_duration_s, 2),
            "git_hash": self.manifest.git_hash,
        }
