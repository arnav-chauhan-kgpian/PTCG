"""
NeuralEvaluator — value head of a trained joint network.

Implements EvaluatorProtocol so it slots into MCTSSearch without further
changes.  Internally it delegates to the same shared ``NetworkWrapper``
that ``NeuralPriorPolicy`` uses; the optional ``InferenceCache`` ensures a
state is never encoded or forward-passed twice.

Returned value is in [0, 1] (sigmoid output) from the perspective of
``state.current_player``.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from src.mcts.node import MCTSAction

if TYPE_CHECKING:
    from src.game_state.state import GameState
    from src.mcts.features import FeatureEncoderProtocol
    from src.mcts.inference_cache import InferenceCache
    from src.mcts.network import NetworkWrapper


def _softmax(logits: list[float]) -> list[float]:
    if not logits:
        return []
    m = max(logits)
    exps = [math.exp(x - m) for x in logits]
    s = sum(exps) or 1.0
    return [e / s for e in exps]


class NeuralEvaluator:
    """
    Value evaluator backed by a NetworkWrapper.

    The evaluator's ``evaluate(state, legal_actions)`` returns:
        value : sigmoid output of the value head
        priors : softmax-normalised, illegal-action-masked policy slice

    A shared ``InferenceCache`` may be supplied so this evaluator and the
    paired NeuralPriorPolicy share a single forward pass per state.
    """

    is_neural = True

    def __init__(
        self,
        network: NetworkWrapper,
        feature_encoder: FeatureEncoderProtocol,
        action_map: list[MCTSAction] | None = None,
        cache: InferenceCache | None = None,
    ) -> None:
        self.network = network
        self.feature_encoder = feature_encoder
        self.cache = cache
        # action_map[i] = the MCTSAction associated with policy logit index i
        self.action_map = action_map or []
        self.call_count = 0
        self.cache_hits = 0
        self.cache_misses = 0

    # ------------------------------------------------------------------ #
    # EvaluatorProtocol
    # ------------------------------------------------------------------ #

    def evaluate(
        self,
        state: GameState,
        legal_actions: list[MCTSAction],
    ) -> tuple[float, dict[MCTSAction, float]]:
        self.call_count += 1
        policy_logits, value = self._infer(state)
        priors = self._mask_and_renormalize(policy_logits, legal_actions)
        return value, priors

    def value_only(self, state: GameState) -> float:
        _, value = self._infer(state)
        return value

    # ------------------------------------------------------------------ #
    # Internal — shared inference path
    # ------------------------------------------------------------------ #

    def _infer(self, state: GameState) -> tuple[list[float], float]:
        """Return (policy_logits, value), routed through the cache if any."""
        if self.cache is not None:
            cached = self.cache.get_by_state(state)
            if cached is not None:
                self.cache_hits += 1
                return cached
            self.cache_misses += 1

        features = self.feature_encoder.encode(state)
        policy_logits, value = self.network.predict(features)
        result = (list(policy_logits), float(value))

        if self.cache is not None:
            self.cache.put_for_state(state, result[0], result[1])
        return result

    # ------------------------------------------------------------------ #
    # Action masking
    # ------------------------------------------------------------------ #

    def _mask_and_renormalize(
        self,
        logits: list[float],
        legal_actions: list[MCTSAction],
    ) -> dict[MCTSAction, float]:
        if not legal_actions:
            return {}

        # Map legal actions to logit indices via action_map. Unknown actions
        # receive the mean logit so the network can still place mass on them.
        if self.action_map:
            mean_logit = sum(logits) / len(logits) if logits else 0.0
            legal_logits: list[float] = []
            for action in legal_actions:
                idx = self._action_index(action)
                legal_logits.append(logits[idx] if idx is not None else mean_logit)
        else:
            # No action map — uniform over legal moves
            legal_logits = [0.0] * len(legal_actions)

        probs = _softmax(legal_logits)
        return dict(zip(legal_actions, probs))

    def _action_index(self, action: MCTSAction) -> int | None:
        try:
            return self.action_map.index(action)
        except ValueError:
            return None

    # ------------------------------------------------------------------ #
    # Diagnostics
    # ------------------------------------------------------------------ #

    def summary(self) -> dict:
        return {
            "call_count": self.call_count,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "num_parameters": getattr(self.network, "num_parameters", 0),
            "device": getattr(self.network, "device", "cpu"),
            "has_action_map": bool(self.action_map),
        }
