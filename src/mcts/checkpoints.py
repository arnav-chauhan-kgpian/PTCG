"""
Checkpoint manager for the joint network.

Wraps torch.save / torch.load with metadata so checkpoints remain
self-describing across training runs:

  • training step
  • timestamp (passed in — see ``CheckpointMetadata.now``)
  • git commit hash (when available)
  • network config
  • optional training config snapshot

Importable without PyTorch installed: ``CheckpointMetadata`` and
``CheckpointManager`` raise a clear ImportError on save/load only.
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING

try:
    import torch
    _HAS_TORCH = True
except ImportError:
    torch = None  # type: ignore[assignment]
    _HAS_TORCH = False

if TYPE_CHECKING:
    from src.mcts.network import NetworkWrapper


# -------------------------------------------------------------------------
# Metadata
# -------------------------------------------------------------------------

def _git_hash(short: bool = True) -> str | None:
    try:
        cmd = ["git", "rev-parse", "--short" if short else "--verify", "HEAD"]
        out = subprocess.check_output(
            cmd, cwd=os.getcwd(), stderr=subprocess.DEVNULL, timeout=2,
        )
        return out.decode("utf-8").strip()
    except Exception:
        return None


@dataclass(frozen=True)
class CheckpointMetadata:
    """Self-describing checkpoint header."""
    training_step: int = 0
    timestamp: str = ""                  # ISO-8601 string (caller-supplied)
    git_hash: str | None = None
    network_config: dict = field(default_factory=dict)
    training_config: dict = field(default_factory=dict)
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> CheckpointMetadata:
        return cls(**{k: data.get(k, v) for k, v in cls().to_dict().items()})


# -------------------------------------------------------------------------
# Manager
# -------------------------------------------------------------------------

class CheckpointManager:
    """
    Persist and restore ``NetworkWrapper`` instances under a directory.

    Layout::

        <root>/
            ckpt_000001.pt
            ckpt_000001.meta.json
            ckpt_000002.pt
            ckpt_000002.meta.json
            latest -> ckpt_000002.pt
    """

    def __init__(
        self,
        root: str | pathlib.Path,
        keep_last: int = 5,
    ) -> None:
        if not _HAS_TORCH:
            raise ImportError("PyTorch required for CheckpointManager")
        self.root = pathlib.Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.keep_last = keep_last

    # ------------------------------------------------------------------ #
    # Saving
    # ------------------------------------------------------------------ #

    def save(
        self,
        network: NetworkWrapper,
        metadata: CheckpointMetadata | None = None,
        name: str | None = None,
    ) -> pathlib.Path:
        meta = metadata or CheckpointMetadata()
        if not meta.network_config:
            meta = CheckpointMetadata(
                **{**meta.to_dict(), "network_config": dict(network.config.__dict__)}
            )
        if meta.git_hash is None:
            meta = CheckpointMetadata(
                **{**meta.to_dict(), "git_hash": _git_hash()}
            )

        idx = meta.training_step
        base = name or f"ckpt_{idx:06d}"
        weight_path = self.root / f"{base}.pt"
        meta_path = self.root / f"{base}.meta.json"

        torch.save({
            "model_state": network.state_dict(),
            "metadata": meta.to_dict(),
        }, weight_path)
        meta_path.write_text(json.dumps(meta.to_dict(), indent=2), encoding="utf-8")

        self._update_latest(weight_path)
        self._prune()
        return weight_path

    # ------------------------------------------------------------------ #
    # Loading
    # ------------------------------------------------------------------ #

    def load(
        self,
        name: str,
        device: str = "auto",
    ) -> tuple[NetworkWrapper, CheckpointMetadata]:
        from src.mcts.network import NetworkConfig, NetworkWrapper
        path = self.root / (name if name.endswith(".pt") else f"{name}.pt")
        if not path.exists():
            raise FileNotFoundError(f"Checkpoint not found: {path}")
        if path.suffix != ".pt":
            raise ValueError(f"Refusing to load non-.pt checkpoint: {path}")
        # weights_only=True restricts unpickling to safe tensor types only,
        # preventing arbitrary code execution from a malicious checkpoint
        # (CVE-2025-32434 / pickle-RCE class). Our checkpoint payload is a
        # plain dict of {"model_state": state_dict, "metadata": dict[str, primitive]}
        # which is fully covered by the safe allowlist.
        payload = torch.load(path, map_location="cpu", weights_only=True)
        meta = CheckpointMetadata.from_dict(payload.get("metadata", {}))
        cfg_dict = dict(meta.network_config)
        if device != "auto":
            cfg_dict["device"] = device
        cfg = NetworkConfig(**cfg_dict)
        wrapper = NetworkWrapper(cfg)
        wrapper.load_state_dict(payload["model_state"])
        return wrapper, meta

    def load_latest(self, device: str = "auto") -> tuple[NetworkWrapper, CheckpointMetadata]:
        latest = self.root / "latest"
        if latest.is_symlink() or (latest.exists() and latest.suffix == ".pt"):
            real = latest.resolve()
            return self.load(real.stem, device=device)
        if latest.exists() and latest.is_file():
            # Plain text pointer fallback (Windows without symlink privilege)
            target = latest.read_text(encoding="utf-8").strip()
            stem = target[:-3] if target.endswith(".pt") else target
            return self.load(stem, device=device)
        # Fallback: sort checkpoints by name
        candidates = sorted(self.root.glob("ckpt_*.pt"))
        if not candidates:
            raise FileNotFoundError(f"No checkpoints in {self.root}")
        return self.load(candidates[-1].stem, device=device)

    # ------------------------------------------------------------------ #
    # Listing / pruning
    # ------------------------------------------------------------------ #

    def list_checkpoints(self) -> list[pathlib.Path]:
        return sorted(self.root.glob("ckpt_*.pt"))

    def _update_latest(self, target: pathlib.Path) -> None:
        latest = self.root / "latest"
        try:
            if latest.exists() or latest.is_symlink():
                latest.unlink()
            latest.symlink_to(target.name)
        except (OSError, NotImplementedError):
            # Windows without symlink privileges → write a plain pointer file
            (self.root / "latest").write_text(target.name, encoding="utf-8")

    def _prune(self) -> None:
        ckpts = self.list_checkpoints()
        if len(ckpts) <= self.keep_last:
            return
        for old in ckpts[: -self.keep_last]:
            try:
                old.unlink()
                meta = self.root / f"{old.stem}.meta.json"
                if meta.exists():
                    meta.unlink()
            except OSError:
                pass

    # ------------------------------------------------------------------ #
    # Diagnostics
    # ------------------------------------------------------------------ #

    def summary(self) -> dict:
        return {
            "root": str(self.root),
            "n_checkpoints": len(self.list_checkpoints()),
            "keep_last": self.keep_last,
        }
