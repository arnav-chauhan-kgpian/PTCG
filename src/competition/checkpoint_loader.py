"""
Checkpoint loading for competition mode.

Wraps Phase 9 ``NetworkWrapper.load`` with a strict validation step.
Gracefully degrades to a randomly-initialised network if no checkpoint
path is supplied (useful for smoke tests and CI).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.mcts.network import NetworkWrapper


@dataclass
class LoadedCheckpoint:
    network: NetworkWrapper
    source: str            # "file" | "fresh"
    description: str = ""

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "description": self.description,
            "num_parameters": getattr(self.network, "num_parameters", 0),
            "device": getattr(self.network, "device", "cpu"),
        }


class CheckpointLoader:
    """Loads checkpoints for competition inference."""

    def load(
        self,
        path: str | None = None,
        *,
        device: str = "auto",
    ) -> LoadedCheckpoint:
        from src.mcts.network import NetworkConfig, NetworkWrapper, has_torch
        if not has_torch():
            raise ImportError("PyTorch is required for CheckpointLoader")
        if path is None:
            wrapper = NetworkWrapper(NetworkConfig(device=device))
            return LoadedCheckpoint(
                network=wrapper, source="fresh",
                description="Untrained network (no checkpoint supplied)",
            )
        try:
            wrapper = NetworkWrapper.load(path, device=device)
            return LoadedCheckpoint(
                network=wrapper, source="file",
                description=f"Loaded from {path}",
            )
        except Exception as exc:
            raise RuntimeError(f"Failed to load checkpoint {path!r}: {exc}") from exc
