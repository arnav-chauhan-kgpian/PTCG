"""
Loss functions for AlphaZero-style joint policy + value training.

All losses are pure PyTorch and importable only when ``torch`` is
available.  ``has_torch()`` exposes the gate so callers can fall back to
heuristic-only training.

Equations
---------
    policy_loss   = -mean(sum(π_target * log_softmax(policy_logits)))
    value_loss_mse = mean((v_pred - v_target)^2)
    value_loss_bce = -mean(v_target * log(v_pred) + (1-v_target) * log(1-v_pred))
    entropy_bonus  = -mean(sum(softmax(logits) * log_softmax(logits)))
    l2            = sum(p^2 for p in params)
    total         = w_p · policy_loss + w_v · value_loss − β · entropy_bonus
"""

from __future__ import annotations

from dataclasses import dataclass

try:
    import torch
    import torch.nn.functional as F
    _HAS_TORCH = True
except ImportError:
    torch = None  # type: ignore[assignment]
    F = None  # type: ignore[assignment]
    _HAS_TORCH = False


def has_torch() -> bool:
    return _HAS_TORCH


# -------------------------------------------------------------------------
# Per-term losses
# -------------------------------------------------------------------------

def policy_cross_entropy(logits, target_probs, eps: float = 1e-9):
    """Cross-entropy between softmax(logits) and target distribution."""
    log_probs = F.log_softmax(logits, dim=-1)
    return -(target_probs * log_probs).sum(dim=-1).mean()


def value_mse(value_pred, value_target):
    """Mean-squared error between value predictions and targets."""
    return F.mse_loss(value_pred.view(-1), value_target.view(-1))


def value_bce(value_pred, value_target, eps: float = 1e-7):
    """
    Binary cross-entropy on values clipped to (eps, 1-eps).
    Assumes value_pred is already in [0, 1] (sigmoid output).
    """
    v = value_pred.view(-1).clamp(eps, 1.0 - eps)
    t = value_target.view(-1).clamp(0.0, 1.0)
    return -(t * torch.log(v) + (1.0 - t) * torch.log(1.0 - v)).mean()


def entropy_bonus(logits):
    """Higher entropy = flatter distribution. Negated for maximisation."""
    probs = F.softmax(logits, dim=-1)
    log_probs = F.log_softmax(logits, dim=-1)
    return -(probs * log_probs).sum(dim=-1).mean()


def l2_penalty(parameters) -> torch.Tensor:
    """Sum of squared parameters (weight decay added explicitly to loss)."""
    total = None
    for p in parameters:
        if p.requires_grad:
            term = (p * p).sum()
            total = term if total is None else total + term
    return total if total is not None else torch.tensor(0.0)


# -------------------------------------------------------------------------
# Combined AlphaZero loss
# -------------------------------------------------------------------------

@dataclass(frozen=True)
class LossWeights:
    policy: float = 1.0
    value: float = 1.0
    entropy: float = 0.0           # subtracted: positive β encourages exploration
    l2: float = 0.0                # explicit L2 on top of optimizer weight_decay


@dataclass(frozen=True)
class LossOutput:
    """Decomposed loss values for logging."""
    total: float
    policy: float
    value: float
    entropy: float
    l2: float

    def to_dict(self) -> dict:
        return {
            "total": self.total, "policy": self.policy, "value": self.value,
            "entropy": self.entropy, "l2": self.l2,
        }


class AlphaZeroLoss:
    """
    Composite loss used by the trainer.

    Configure once with weights, then call ``compute(logits, value_pred,
    policy_target, value_target, parameters=None)``.  Returns a tuple
    ``(scalar_tensor, LossOutput)``.
    """

    def __init__(
        self,
        weights: LossWeights | None = None,
        value_loss: str = "mse",     # "mse" | "bce"
    ) -> None:
        if not _HAS_TORCH:
            raise ImportError("PyTorch required for AlphaZeroLoss")
        self.weights = weights or LossWeights()
        if value_loss not in ("mse", "bce"):
            raise ValueError(f"value_loss must be 'mse' or 'bce', got {value_loss!r}")
        self.value_loss = value_loss

    def compute(
        self,
        policy_logits,
        value_pred,
        policy_target,
        value_target,
        parameters=None,
    ):
        p_loss = policy_cross_entropy(policy_logits, policy_target)
        if self.value_loss == "mse":
            v_loss = value_mse(value_pred, value_target)
        else:
            v_loss = value_bce(value_pred, value_target)

        ent = entropy_bonus(policy_logits)
        l2 = (l2_penalty(parameters)
              if parameters is not None and self.weights.l2 > 0
              else torch.tensor(0.0))

        total = (
            self.weights.policy * p_loss
            + self.weights.value * v_loss
            - self.weights.entropy * ent
            + self.weights.l2 * l2
        )
        decomposed = LossOutput(
            total=float(total.detach().cpu().item()),
            policy=float(p_loss.detach().cpu().item()),
            value=float(v_loss.detach().cpu().item()),
            entropy=float(ent.detach().cpu().item()),
            l2=float(l2.detach().cpu().item()) if l2 is not None else 0.0,
        )
        return total, decomposed
