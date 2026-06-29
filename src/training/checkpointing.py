"""
Pipeline-level checkpointing.

Distinct from Phase 9's ``CheckpointManager`` (which persists individual
networks), this module owns *training state* checkpoints: the trainer step
counter, replay buffer, metrics, best network ref, and config.

A resume from a pipeline checkpoint must restore everything needed to
continue training as if uninterrupted.
"""

from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass, field


@dataclass
class PipelineCheckpoint:
    """Self-describing pipeline-state snapshot."""

    round_index: int = 0
    training_step: int = 0
    best_checkpoint_name: str | None = None
    candidate_checkpoint_name: str | None = None
    metrics_snapshot: dict = field(default_factory=dict)
    config_snapshot: dict = field(default_factory=dict)
    replay_buffer_path: str | None = None
    timestamp: str = ""
    git_hash: str | None = None
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "round_index": self.round_index,
            "training_step": self.training_step,
            "best_checkpoint_name": self.best_checkpoint_name,
            "candidate_checkpoint_name": self.candidate_checkpoint_name,
            "metrics_snapshot": self.metrics_snapshot,
            "config_snapshot": self.config_snapshot,
            "replay_buffer_path": self.replay_buffer_path,
            "timestamp": self.timestamp,
            "git_hash": self.git_hash,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict) -> PipelineCheckpoint:
        return cls(**{
            **{f: cls().to_dict()[f] for f in cls().to_dict()},
            **{k: v for k, v in data.items() if k in cls().to_dict()},
        })


class PipelineCheckpointStore:
    """Persists/loads ``PipelineCheckpoint`` snapshots as JSON files."""

    def __init__(self, root) -> None:
        self.root = pathlib.Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, ckpt: PipelineCheckpoint, name: str | None = None) -> pathlib.Path:
        base = name or f"pipeline_{ckpt.round_index:06d}"
        path = self.root / f"{base}.json"
        path.write_text(json.dumps(ckpt.to_dict(), indent=2), encoding="utf-8")
        latest = self.root / "latest.json"
        latest.write_text(path.name, encoding="utf-8")
        return path

    def load(self, name: str) -> PipelineCheckpoint:
        path = self.root / (name if name.endswith(".json") else f"{name}.json")
        data = json.loads(path.read_text(encoding="utf-8"))
        return PipelineCheckpoint.from_dict(data)

    def load_latest(self) -> PipelineCheckpoint | None:
        latest = self.root / "latest.json"
        if latest.exists():
            target = latest.read_text(encoding="utf-8").strip()
            stem = target[:-5] if target.endswith(".json") else target
            return self.load(stem)
        candidates = sorted(self.root.glob("pipeline_*.json"))
        if not candidates:
            return None
        return self.load(candidates[-1].stem)

    def list_checkpoints(self) -> list[pathlib.Path]:
        return sorted(self.root.glob("pipeline_*.json"))
