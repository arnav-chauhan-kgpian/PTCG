"""
Evaluator protocol and heuristic implementations.

The evaluator returns (value, prior_dict) for any leaf node.  Currently
only heuristic evaluators are implemented.  Phase 9 (policy/value network)
will plug in by implementing EvaluatorProtocol.

Value convention
----------------
All values are from the perspective of ``state.current_player``:
  1.0  → certain win for current player
  0.5  → equal position
  0.0  → certain loss for current player
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from src.mcts.node import MCTSAction

if TYPE_CHECKING:
    from src.game_state.state import GameState


# -------------------------------------------------------------------------
# Protocol
# -------------------------------------------------------------------------

@runtime_checkable
class EvaluatorProtocol(Protocol):
    """
    Interface for any position evaluator.

    Returns
    -------
    value : float in [0, 1]
        Estimated probability that current_player wins from this position.
    priors : dict[MCTSAction, float]
        Prior probability for each legal action (need not sum to 1;
        will be normalised by the expansion phase).
    """

    def evaluate(
        self,
        state: GameState,
        legal_actions: list[MCTSAction],
    ) -> tuple[float, dict[MCTSAction, float]]:
        ...


# -------------------------------------------------------------------------
# Uniform (baseline)
# -------------------------------------------------------------------------

class UniformEvaluator:
    """Returns 0.5 for all positions — pure rollout baseline."""

    def evaluate(
        self, state: GameState, legal_actions: list[MCTSAction]
    ) -> tuple[float, dict[MCTSAction, float]]:
        n = len(legal_actions)
        priors = dict.fromkeys(legal_actions, 1.0 / n) if n else {}
        return 0.5, priors


# -------------------------------------------------------------------------
# Heuristic
# -------------------------------------------------------------------------

def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


class HeuristicEvaluator:
    """
    Signal-based heuristic evaluator operating on Phase 7 GameState.

    Signals (from current player's perspective)
    -------------------------------------------
    1. Prize race         weight 0.40   — prizes remaining delta
    2. Active HP          weight 0.20   — active Pokémon HP advantage
    3. Bench size         weight 0.10   — bench count advantage
    4. Hand advantage     weight 0.10   — hand count advantage
    5. Energy advantage   weight 0.10   — attached energy delta
    6. Damage pressure    weight 0.10   — damage on opponent's active

    All signals are individually bounded to [−1, +1] before weighting.
    The weighted sum is passed through a sigmoid centred at 0 → [0, 1].
    Prior probabilities are uniform over legal actions.
    """

    WEIGHTS = {
        "prize_race":    0.40,
        "active_hp":     0.20,
        "bench_size":    0.10,
        "hand":          0.10,
        "energy":        0.10,
        "dmg_pressure":  0.10,
    }
    TEMPERATURE = 1.5  # sigmoid steepness

    def evaluate(
        self, state: GameState, legal_actions: list[MCTSAction]
    ) -> tuple[float, dict[MCTSAction, float]]:
        signals = self._compute_signals(state)
        raw = sum(self.WEIGHTS[k] * signals.get(k, 0.0) for k in self.WEIGHTS)
        value = _sigmoid(raw * self.TEMPERATURE)
        n = len(legal_actions)
        priors = dict.fromkeys(legal_actions, 1.0 / n) if n else {}
        return value, priors

    def _compute_signals(self, state: GameState) -> dict[str, float]:
        p = state.current_player
        me = state.players[p]
        opp = state.players[1 - p]
        instances = state.card_instances

        # 1. Prize race: negative = I'm winning (fewer prizes left)
        prize_delta = opp.prizes_remaining - me.prizes_remaining  # + = I'm ahead
        prize_signal = prize_delta / 6.0  # in [−1, +1]

        # 2. Active HP advantage
        def _active_hp_ratio(player_state) -> float:
            if player_state.active and player_state.active in instances:
                inst = instances[player_state.active]
                return inst.hp_ratio
            return 0.0

        my_hp = _active_hp_ratio(me)
        opp_hp = _active_hp_ratio(opp)
        hp_signal = my_hp - opp_hp  # in [−1, +1]

        # 3. Bench size advantage
        bench_signal = (len(me.bench) - len(opp.bench)) / 5.0

        # 4. Hand advantage (more hand = more options)
        max_hand = max(me.hand_count, opp.hand_count, 1)
        hand_signal = (me.hand_count - opp.hand_count) / max(max_hand, 1)

        # 5. Energy advantage (count all attached energies on my board)
        def _energy_count(player_state) -> int:
            total = 0
            for iid in player_state.all_pokemon_ids:
                inst = instances.get(iid)
                if inst:
                    total += len(inst.attached_energy_ids)
            return total

        my_energy = _energy_count(me)
        opp_energy = _energy_count(opp)
        energy_signal = (my_energy - opp_energy) / max(my_energy + opp_energy, 1)

        # 6. Damage pressure: how damaged is opponent's active?
        dmg_signal = 0.0
        if opp.active and opp.active in instances:
            inst = instances[opp.active]
            if inst.max_hp > 0:
                dmg_signal = inst.damage_taken / inst.max_hp

        return {
            "prize_race":   max(-1.0, min(1.0, prize_signal)),
            "active_hp":    max(-1.0, min(1.0, hp_signal)),
            "bench_size":   max(-1.0, min(1.0, bench_signal)),
            "hand":         max(-1.0, min(1.0, hand_signal)),
            "energy":       max(-1.0, min(1.0, energy_signal)),
            "dmg_pressure": max(-1.0, min(1.0, dmg_signal)),
        }

    def explain(self, state: GameState) -> dict[str, float]:
        """Return raw signals for debugging."""
        return self._compute_signals(state)


# -------------------------------------------------------------------------
# Neural network placeholder
# -------------------------------------------------------------------------

class NeuralEvaluatorPlaceholder:
    """
    Stub for the future policy/value network (Phase 9).

    Falls back to HeuristicEvaluator until replaced with a real model.
    This class exists so Phase 9 can subclass it and the rest of MCTS
    remains unchanged.
    """

    def __init__(self) -> None:
        self._fallback = HeuristicEvaluator()
        self.call_count = 0

    def evaluate(
        self, state: GameState, legal_actions: list[MCTSAction]
    ) -> tuple[float, dict[MCTSAction, float]]:
        self.call_count += 1
        return self._fallback.evaluate(state, legal_actions)

    @property
    def is_neural(self) -> bool:
        return False


# ── convenience factory ────────────────────────────────────────────────────

def make_evaluator(name: str = "heuristic") -> EvaluatorProtocol:
    mapping = {
        "uniform":  UniformEvaluator,
        "heuristic": HeuristicEvaluator,
        "neural":    NeuralEvaluatorPlaceholder,
    }
    if name not in mapping:
        raise ValueError(f"Unknown evaluator: {name!r}. Options: {list(mapping)}")
    return mapping[name]()
