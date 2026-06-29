"""
Trainer — supervised optimisation loop over a ``ReplayBuffer``.

The trainer is the *inner loop* of the AlphaZero pipeline: it does not
play games or evaluate models.  Given a network and replay buffer it
samples minibatches, computes the joint loss, applies an optimiser step,
and reports decomposed metrics.

Interruptible / resumable: ``state_dict()`` and ``load_state_dict()``
serialise the optimiser, scheduler, and step counter so a training run
can be paused and continued without metric drift.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

try:
    import torch
    _HAS_TORCH = True
except ImportError:
    torch = None  # type: ignore[assignment]
    _HAS_TORCH = False

from src.mcts.training_config import TrainingConfig, build_optimizer, build_scheduler
from src.training.losses import AlphaZeroLoss, LossOutput, LossWeights

if TYPE_CHECKING:
    from src.mcts.network import NetworkWrapper
    from src.mcts.replay_buffer import ReplayBuffer


# -------------------------------------------------------------------------
# State container
# -------------------------------------------------------------------------

@dataclass
class TrainerStepResult:
    step: int
    loss: LossOutput
    learning_rate: float
    grad_norm: float = 0.0
    batch_size: int = 0

    def to_dict(self) -> dict:
        return {
            "step": self.step,
            "lr": self.learning_rate,
            "grad_norm": round(self.grad_norm, 6),
            "batch_size": self.batch_size,
            **{f"loss_{k}": v for k, v in self.loss.to_dict().items()},
        }


# -------------------------------------------------------------------------
# Trainer
# -------------------------------------------------------------------------

class Trainer:
    """
    Supervised trainer for the joint policy/value network.

    One ``step()`` call:
        1. samples a minibatch from the replay buffer
        2. forward pass via NetworkWrapper.model
        3. AlphaZeroLoss.compute(...)
        4. backward + grad-clip + optimizer.step()
        5. optional scheduler.step()
        6. returns a TrainerStepResult for logging
    """

    def __init__(
        self,
        network: NetworkWrapper,
        replay_buffer: ReplayBuffer,
        config: TrainingConfig | None = None,
        loss_weights: LossWeights | None = None,
        value_loss: str = "mse",
    ) -> None:
        if not _HAS_TORCH:
            raise ImportError("PyTorch required for Trainer")
        self.network = network
        self.replay = replay_buffer
        self.config = config or TrainingConfig()
        self.optimizer = build_optimizer(self.network.model.parameters(), self.config)
        self.scheduler = build_scheduler(self.optimizer, self.config)
        self.loss_fn = AlphaZeroLoss(loss_weights, value_loss=value_loss)
        self.step_count = 0
        self.epoch_count = 0
        self._device = self.network.device
        self._use_amp = (
            self.config.resolve_device().startswith("cuda")
            and self.config.optimizer.lower() != "sgd"
            and hasattr(torch.cuda, "amp")
            and getattr(self.network.config, "use_mixed_precision", False)
        )
        self._scaler = torch.amp.GradScaler("cuda") if self._use_amp else None

    # ------------------------------------------------------------------ #
    # Single step
    # ------------------------------------------------------------------ #

    def step(self) -> TrainerStepResult | None:
        """Run one optimiser step. Returns None if the buffer is too small."""
        if not self.replay.is_ready(self.config.min_replay_size):
            return None

        bs = self.config.batch_size
        features, policies, values = self.replay.sample_features_targets(bs)
        if not features:
            return None

        x = torch.tensor(features, dtype=torch.float32, device=self._device)
        p_t = torch.tensor(policies, dtype=torch.float32, device=self._device)
        v_t = torch.tensor(values, dtype=torch.float32, device=self._device)

        self.network.model.train()
        self.optimizer.zero_grad(set_to_none=True)

        if self._use_amp:
            with torch.autocast(device_type="cuda"):
                logits, v_pred = self.network.model(x)
                total, decomposed = self.loss_fn.compute(
                    logits, v_pred, p_t, v_t,
                    parameters=self.network.model.parameters() if self.loss_fn.weights.l2 > 0 else None,
                )
            self._scaler.scale(total).backward()
            self._scaler.unscale_(self.optimizer)
            grad_norm = torch.nn.utils.clip_grad_norm_(
                self.network.model.parameters(), self.config.grad_clip,
            )
            self._scaler.step(self.optimizer)
            self._scaler.update()
        else:
            logits, v_pred = self.network.model(x)
            total, decomposed = self.loss_fn.compute(
                logits, v_pred, p_t, v_t,
                parameters=self.network.model.parameters() if self.loss_fn.weights.l2 > 0 else None,
            )
            total.backward()
            grad_norm = torch.nn.utils.clip_grad_norm_(
                self.network.model.parameters(), self.config.grad_clip,
            )
            self.optimizer.step()

        if self.scheduler is not None:
            self.scheduler.step()

        self.network.model.eval()
        self.step_count += 1

        return TrainerStepResult(
            step=self.step_count,
            loss=decomposed,
            learning_rate=self._current_lr(),
            grad_norm=float(grad_norm),
            batch_size=len(features),
        )

    # ------------------------------------------------------------------ #
    # Epoch / multi-step driver
    # ------------------------------------------------------------------ #

    def train_epoch(self) -> list[TrainerStepResult]:
        """Run ``iterations_per_epoch`` steps and return per-step results."""
        results: list[TrainerStepResult] = []
        for _ in range(self.config.iterations_per_epoch):
            r = self.step()
            if r is None:
                break
            results.append(r)
        self.epoch_count += 1
        return results

    # ------------------------------------------------------------------ #
    # State persistence
    # ------------------------------------------------------------------ #

    def state_dict(self) -> dict:
        sd = {
            "step_count": self.step_count,
            "epoch_count": self.epoch_count,
            "optimizer": self.optimizer.state_dict(),
        }
        if self.scheduler is not None and hasattr(self.scheduler, "state_dict"):
            sd["scheduler"] = self.scheduler.state_dict()
        return sd

    def load_state_dict(self, sd: dict) -> None:
        self.step_count = int(sd.get("step_count", 0))
        self.epoch_count = int(sd.get("epoch_count", 0))
        if "optimizer" in sd:
            self.optimizer.load_state_dict(sd["optimizer"])
        if "scheduler" in sd and self.scheduler is not None:
            try:
                self.scheduler.load_state_dict(sd["scheduler"])
            except Exception:
                pass

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _current_lr(self) -> float:
        for group in self.optimizer.param_groups:
            return float(group["lr"])
        return 0.0
