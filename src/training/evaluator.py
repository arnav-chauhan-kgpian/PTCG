"""
Offline evaluator — runs the policy/value network against a held-out
replay buffer to compute supervised losses and policy/value agreement.

Distinct from ``Arena`` (which plays games).  Useful for monitoring
progress without spending compute on full self-play.
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

if TYPE_CHECKING:
    from src.mcts.network import NetworkWrapper
    from src.mcts.replay_buffer import ReplayBuffer


@dataclass
class EvaluationResult:
    policy_loss: float = 0.0
    value_loss: float = 0.0
    value_mae: float = 0.0
    samples: int = 0
    top1_agreement: float = 0.0     # fraction of samples whose argmax matches policy_target argmax

    def to_dict(self) -> dict:
        return {
            "policy_loss": round(self.policy_loss, 6),
            "value_loss": round(self.value_loss, 6),
            "value_mae": round(self.value_mae, 6),
            "samples": self.samples,
            "top1_agreement": round(self.top1_agreement, 4),
        }


def evaluate(
    network: NetworkWrapper,
    buffer: ReplayBuffer,
    batch_size: int = 256,
    max_batches: int | None = None,
) -> EvaluationResult:
    """Run the network over batches drawn from *buffer* and aggregate losses."""
    if not _HAS_TORCH:
        raise ImportError("PyTorch required for evaluate()")
    if len(buffer) == 0:
        return EvaluationResult()

    n = len(buffer)
    if max_batches is None:
        max_batches = max(1, (n + batch_size - 1) // batch_size)

    network.model.eval()
    total_p = 0.0
    total_v = 0.0
    total_mae = 0.0
    total_top1 = 0
    seen = 0

    with torch.no_grad():
        for _ in range(max_batches):
            features, policies, values = buffer.sample_features_targets(batch_size)
            if not features:
                break
            x = torch.tensor(features, dtype=torch.float32, device=network.device)
            p_t = torch.tensor(policies, dtype=torch.float32, device=network.device)
            v_t = torch.tensor(values, dtype=torch.float32, device=network.device)

            logits, v_pred = network.model(x)
            log_probs = torch.log_softmax(logits, dim=-1)
            policy_loss = -(p_t * log_probs).sum(dim=-1).mean()
            value_loss = torch.mean((v_pred.view(-1) - v_t) ** 2)
            value_mae = torch.mean(torch.abs(v_pred.view(-1) - v_t))

            pred_top1 = logits.argmax(dim=-1)
            target_top1 = p_t.argmax(dim=-1)
            top1_agree = (pred_top1 == target_top1).sum().item()

            bs = x.size(0)
            total_p += float(policy_loss.item()) * bs
            total_v += float(value_loss.item()) * bs
            total_mae += float(value_mae.item()) * bs
            total_top1 += top1_agree
            seen += bs

    if seen == 0:
        return EvaluationResult()
    return EvaluationResult(
        policy_loss=total_p / seen,
        value_loss=total_v / seen,
        value_mae=total_mae / seen,
        samples=seen,
        top1_agreement=total_top1 / seen,
    )
