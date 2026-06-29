"""
Prior policies — assign initial action probabilities before any visits.

During expansion, each newly created child receives a prior probability
P(s, a) used by PUCT selection.  This module provides:

    UniformPriorPolicy   : equal probability to all actions (default)
    HeuristicPriorPolicy : action type ranking as a weak prior
    NeuralPriorPlaceholder : stub for Phase 9 policy network

Future phases plug in by replacing NeuralPriorPlaceholder with a model
that takes a feature vector and returns a probability distribution.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from src.mcts.node import MCTSAction

if TYPE_CHECKING:
    from src.game_state.state import GameState


# -------------------------------------------------------------------------
# Protocol
# -------------------------------------------------------------------------

class PriorPolicy(Protocol):
    """
    Returns a prior probability distribution over legal actions.

    The distribution need not sum to 1; the expansion phase normalises it.
    """

    def prior_distribution(
        self,
        state: GameState,
        legal_actions: list[MCTSAction],
    ) -> dict[MCTSAction, float]:
        ...


# -------------------------------------------------------------------------
# Uniform (default)
# -------------------------------------------------------------------------

class UniformPriorPolicy:
    """Assign equal probability to all legal actions."""

    def prior_distribution(
        self, state: GameState, legal_actions: list[MCTSAction]
    ) -> dict[MCTSAction, float]:
        n = len(legal_actions)
        if n == 0:
            return {}
        p = 1.0 / n
        return dict.fromkeys(legal_actions, p)


# -------------------------------------------------------------------------
# Heuristic prior
# -------------------------------------------------------------------------

# Action type priority order (higher = more likely to be good a priori)
_ACTION_PRIORITY: dict[str, float] = {
    "attack":          1.0,
    "evolve":          0.9,
    "attach_energy":   0.8,
    "use_ability":     0.75,
    "play_pokemon":    0.7,
    "play_supporter":  0.65,
    "play_item":       0.55,
    "retreat":         0.4,
    "play_stadium":    0.35,
    "end_turn":        0.1,
    "pass":            0.05,
}


class HeuristicPriorPolicy:
    """
    Assign priors based on action type ranking.

    This provides a weak but fast signal: attack > evolve > attach > ...
    Normalised to a probability distribution before returning.
    """

    def prior_distribution(
        self, state: GameState, legal_actions: list[MCTSAction]
    ) -> dict[MCTSAction, float]:
        if not legal_actions:
            return {}

        raw = {
            a: _ACTION_PRIORITY.get(a.action_type, 0.3)
            for a in legal_actions
        }
        total = sum(raw.values()) or 1.0
        return {a: v / total for a, v in raw.items()}


# -------------------------------------------------------------------------
# Neural network placeholder
# -------------------------------------------------------------------------

class NeuralPriorPlaceholder:
    """
    Stub for the Phase 9 policy network.

    Falls back to HeuristicPriorPolicy until the real model is available.
    Exposes ``call_count`` for profiling and ``is_neural`` flag so the
    search engine can log whether neural priors are active.
    """

    def __init__(self) -> None:
        self._fallback = HeuristicPriorPolicy()
        self.call_count = 0

    @property
    def is_neural(self) -> bool:
        return False

    def prior_distribution(
        self, state: GameState, legal_actions: list[MCTSAction]
    ) -> dict[MCTSAction, float]:
        self.call_count += 1
        return self._fallback.prior_distribution(state, legal_actions)


# ── Factory ─────────────────────────────────────────────────────────────────

def make_prior_policy(name: str = "uniform") -> PriorPolicy:
    mapping = {
        "uniform":   UniformPriorPolicy,
        "heuristic": HeuristicPriorPolicy,
        "neural":    NeuralPriorPlaceholder,
    }
    if name not in mapping:
        raise ValueError(f"Unknown prior policy: {name!r}. Options: {list(mapping)}")
    return mapping[name]()
