"""
Training-loop hyperparameters.

This module owns the *training* configuration only.  Network architecture
lives in ``network.NetworkConfig``; MCTS search hyperparameters live in
``config.MCTSConfig``.  Keeping them separate lets each component be
versioned independently.

No PyTorch import is required at module load time — the config is a pure
dataclass.  ``build_optimizer`` and ``build_scheduler`` raise a clear
ImportError when torch is missing.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

try:
    import torch
    _HAS_TORCH = True
except ImportError:
    torch = None  # type: ignore[assignment]
    _HAS_TORCH = False


@dataclass(frozen=True)
class TrainingConfig:
    """Hyperparameters for one training run."""

    # Optimizer
    optimizer: str = "adam"           # "adam" | "sgd" | "adamw"
    learning_rate: float = 1e-3
    weight_decay: float = 1e-4
    momentum: float = 0.9             # used by SGD only

    # Scheduler
    scheduler: str = "none"           # "none" | "step" | "cosine" | "exponential"
    scheduler_step_size: int = 50
    scheduler_gamma: float = 0.5
    scheduler_t_max: int = 100

    # Training loop
    batch_size: int = 256
    epochs: int = 1
    iterations_per_epoch: int = 100
    grad_clip: float = 1.0
    value_loss_weight: float = 1.0
    policy_loss_weight: float = 1.0
    entropy_bonus: float = 0.0

    # Data
    min_replay_size: int = 1000
    max_replay_size: int = 100_000

    # Logging / checkpointing
    log_every: int = 10
    checkpoint_every: int = 100

    # Reproducibility
    seed: int | None = None
    device: str = "auto"

    def with_overrides(self, **kwargs) -> TrainingConfig:
        return replace(self, **kwargs)

    def resolve_device(self) -> str:
        if self.device != "auto":
            return self.device
        if _HAS_TORCH and torch.cuda.is_available():
            return "cuda"
        return "cpu"

    def to_dict(self) -> dict:
        return self.__dict__


# -------------------------------------------------------------------------
# Builders
# -------------------------------------------------------------------------

def build_optimizer(model_params, config: TrainingConfig):
    """Instantiate an optimizer from the config."""
    if not _HAS_TORCH:
        raise ImportError("PyTorch required for build_optimizer")
    name = config.optimizer.lower()
    if name == "adam":
        return torch.optim.Adam(
            model_params,
            lr=config.learning_rate,
            weight_decay=config.weight_decay,
        )
    if name == "adamw":
        return torch.optim.AdamW(
            model_params,
            lr=config.learning_rate,
            weight_decay=config.weight_decay,
        )
    if name == "sgd":
        return torch.optim.SGD(
            model_params,
            lr=config.learning_rate,
            momentum=config.momentum,
            weight_decay=config.weight_decay,
        )
    raise ValueError(f"Unknown optimizer: {config.optimizer!r}")


def build_scheduler(optimizer, config: TrainingConfig):
    """Instantiate a learning-rate scheduler from the config (or None)."""
    if not _HAS_TORCH:
        raise ImportError("PyTorch required for build_scheduler")
    name = config.scheduler.lower()
    if name == "none":
        return None
    if name == "step":
        return torch.optim.lr_scheduler.StepLR(
            optimizer, step_size=config.scheduler_step_size, gamma=config.scheduler_gamma,
        )
    if name == "cosine":
        return torch.optim.lr_scheduler.CosineAnnealingLR(
            optimizer, T_max=config.scheduler_t_max,
        )
    if name == "exponential":
        return torch.optim.lr_scheduler.ExponentialLR(
            optimizer, gamma=config.scheduler_gamma,
        )
    raise ValueError(f"Unknown scheduler: {config.scheduler!r}")
