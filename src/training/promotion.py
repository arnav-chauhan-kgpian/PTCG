"""
Model promotion policy — decides whether a candidate becomes the new best.

Default policy: candidate must score ≥ ``win_rate_threshold`` against the
current best across ≥ ``min_games`` games.  Callable policies may be
plugged in for more elaborate gating.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.training.arena import ArenaResult
    from src.training.config import PromotionConfig


# -------------------------------------------------------------------------
# Decision container
# -------------------------------------------------------------------------

@dataclass(frozen=True)
class PromotionDecision:
    promoted: bool
    candidate_win_rate: float
    candidate_score: float
    threshold: float
    n_games: int
    reason: str

    def to_dict(self) -> dict:
        return {
            "promoted": self.promoted,
            "candidate_win_rate": round(self.candidate_win_rate, 4),
            "candidate_score": round(self.candidate_score, 4),
            "threshold": self.threshold,
            "n_games": self.n_games,
            "reason": self.reason,
        }


# -------------------------------------------------------------------------
# Default policy
# -------------------------------------------------------------------------

class PromotionPolicy:
    """
    Standard AlphaZero promotion gate.

    Pass a custom ``PromotionConfig`` (or supply ``decide_fn`` for custom
    logic) — callers can plug in their own without subclassing.
    """

    def __init__(
        self,
        config: PromotionConfig,
        decide_fn: Callable[[ArenaResult, PromotionConfig], PromotionDecision] | None = None,
    ) -> None:
        self.config = config
        self.decide_fn = decide_fn or _default_decide

    def decide(self, result: ArenaResult) -> PromotionDecision:
        return self.decide_fn(result, self.config)


def _default_decide(result, config) -> PromotionDecision:
    score = result.candidate_score
    n = result.total

    if n < config.min_games:
        return PromotionDecision(
            promoted=False,
            candidate_win_rate=result.candidate_win_rate,
            candidate_score=score,
            threshold=config.win_rate_threshold,
            n_games=n,
            reason=f"insufficient games ({n} < {config.min_games})",
        )

    threshold = config.win_rate_threshold
    if config.require_strict_improvement:
        promoted = score > threshold
        reason = (
            f"score {score:.3f} > threshold {threshold:.3f}"
            if promoted else
            f"score {score:.3f} <= threshold {threshold:.3f}"
        )
    else:
        promoted = score >= threshold
        reason = (
            f"score {score:.3f} >= threshold {threshold:.3f}"
            if promoted else
            f"score {score:.3f} < threshold {threshold:.3f}"
        )

    return PromotionDecision(
        promoted=promoted,
        candidate_win_rate=result.candidate_win_rate,
        candidate_score=score,
        threshold=threshold,
        n_games=n,
        reason=reason,
    )
