"""
Pure-inference engine wrapping ``NeuralEvaluator`` + ``NeuralPriorPolicy``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.mcts.features import FeatureEncoderProtocol
    from src.mcts.network import NetworkWrapper
    from src.mcts.node import MCTSAction


class InferenceEngine:
    """Cached neural inference, ready for MCTS."""

    def __init__(
        self,
        network: NetworkWrapper,
        *,
        encoder: FeatureEncoderProtocol | None = None,
        action_map: list[MCTSAction] | None = None,
        cache_size: int = 50_000,
    ) -> None:
        from src.mcts import (
            GameStateFeatureEncoder,
            InferenceCache,
            NeuralEvaluator,
            NeuralPriorPolicy,
        )
        self.network = network
        self.encoder = encoder or GameStateFeatureEncoder()
        self.cache = InferenceCache(max_size=cache_size)
        self.action_map = action_map or []
        self.evaluator = NeuralEvaluator(
            self.network, self.encoder, self.action_map, self.cache,
        )
        self.prior_policy = NeuralPriorPolicy(
            self.network, self.encoder, self.action_map, self.cache,
        )

    @property
    def cache_hit_rate(self) -> float:
        return self.cache.stats.hit_rate

    def summary(self) -> dict:
        return {
            "num_parameters": getattr(self.network, "num_parameters", 0),
            "device": getattr(self.network, "device", "cpu"),
            "cache_size": len(self.cache),
            "cache_hit_rate": round(self.cache_hit_rate, 4),
        }
