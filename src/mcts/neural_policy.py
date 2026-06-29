"""
NeuralPriorPolicy — policy head of a trained joint network.

Implements ``PriorPolicy`` so it slots into MCTS expansion alongside the
existing UniformPriorPolicy and HeuristicPriorPolicy.  When paired with
``NeuralEvaluator`` and a shared ``InferenceCache`` the two consume a
single forward pass per state.

Illegal-move masking, stable softmax, and batched prediction are all
handled here so MCTS callers see a plain ``dict[MCTSAction, float]``.
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


def _stable_softmax(logits: list[float]) -> list[float]:
    if not logits:
        return []
    m = max(logits)
    exps = [math.exp(x - m) for x in logits]
    s = sum(exps) or 1.0
    return [e / s for e in exps]


class NeuralPriorPolicy:
    """
    Policy prior produced by the joint network's policy head.

    Behaviour
    ---------
    1. Encode the state once (cache-aware).
    2. Look up logits via shared InferenceCache (if any).
    3. Mask logits down to ``legal_actions`` only.
    4. Stable softmax → normalised prior distribution.

    Unknown actions (not in ``action_map``) receive the mean of the legal
    logits so the network can still allocate mass to them.
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
        self.action_map = action_map or []
        self.cache = cache
        self.call_count = 0
        self.cache_hits = 0

    # ------------------------------------------------------------------ #
    # PriorPolicy
    # ------------------------------------------------------------------ #

    def prior_distribution(
        self,
        state: GameState,
        legal_actions: list[MCTSAction],
    ) -> dict[MCTSAction, float]:
        self.call_count += 1
        if not legal_actions:
            return {}

        policy_logits = self._get_logits(state)
        legal_logits = self._mask(policy_logits, legal_actions)
        probs = _stable_softmax(legal_logits)
        return dict(zip(legal_actions, probs))

    # ------------------------------------------------------------------ #
    # Batched prediction
    # ------------------------------------------------------------------ #

    def prior_distribution_batch(
        self,
        states: list[GameState],
        legal_actions_per_state: list[list[MCTSAction]],
    ) -> list[dict[MCTSAction, float]]:
        """
        Batched variant.  Encodes uncached states together and runs one
        forward pass for them.  Cached states reuse their stored logits.
        """
        if not states:
            return []
        results: list[dict[MCTSAction, float] | None] = [None] * len(states)
        to_query: list[tuple[int, tuple[float, ...]]] = []

        for i, state in enumerate(states):
            cached = self.cache.get_by_state(state) if self.cache else None
            if cached is not None:
                self.cache_hits += 1
                logits, _v = cached
                results[i] = self._finalize(logits, legal_actions_per_state[i])
            else:
                to_query.append((i, self.feature_encoder.encode(state)))

        if to_query:
            features = [f for _, f in to_query]
            logits_batch, value_batch = self.network.predict_batch(features)
            for (i, _), logits, value in zip(to_query, logits_batch, value_batch):
                results[i] = self._finalize(logits, legal_actions_per_state[i])
                if self.cache is not None:
                    self.cache.put_for_state(states[i], logits, value)

        return [r or {} for r in results]

    # ------------------------------------------------------------------ #
    # Internal
    # ------------------------------------------------------------------ #

    def _get_logits(self, state: GameState) -> list[float]:
        if self.cache is not None:
            cached = self.cache.get_by_state(state)
            if cached is not None:
                self.cache_hits += 1
                return cached[0]

        features = self.feature_encoder.encode(state)
        logits, value = self.network.predict(features)
        logits_list = list(logits)
        if self.cache is not None:
            self.cache.put_for_state(state, logits_list, float(value))
        return logits_list

    def _mask(self, logits: list[float], legal_actions: list[MCTSAction]) -> list[float]:
        if not self.action_map:
            return [0.0] * len(legal_actions)
        mean_logit = sum(logits) / len(logits) if logits else 0.0
        out: list[float] = []
        for a in legal_actions:
            try:
                idx = self.action_map.index(a)
            except ValueError:
                idx = None
            out.append(logits[idx] if idx is not None else mean_logit)
        return out

    def _finalize(
        self, logits: list[float], legal_actions: list[MCTSAction]
    ) -> dict[MCTSAction, float]:
        legal_logits = self._mask(list(logits), legal_actions)
        probs = _stable_softmax(legal_logits)
        return dict(zip(legal_actions, probs))

    # ------------------------------------------------------------------ #
    # Diagnostics
    # ------------------------------------------------------------------ #

    def summary(self) -> dict:
        return {
            "call_count": self.call_count,
            "cache_hits": self.cache_hits,
            "has_action_map": bool(self.action_map),
        }
