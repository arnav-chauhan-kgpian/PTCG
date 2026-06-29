"""
Rollout policies — simulate from a leaf node to estimate its value.

All rollouts return a value in [0, 1] from the perspective of
``node.player`` (the player whose turn it was at the leaf).

Pluggable interface: any callable matching
    (node, simulator, evaluator, rng, depth) → float
can be used as a rollout.  The RolloutBase protocol makes this explicit.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Protocol

from src.mcts.node import MCTSAction, MCTSNode

if TYPE_CHECKING:
    from src.mcts.evaluator import EvaluatorProtocol
    from src.mcts.simulation import SimulatorProtocol


# -------------------------------------------------------------------------
# Protocol
# -------------------------------------------------------------------------

class RolloutBase(Protocol):
    def rollout(
        self,
        node: MCTSNode,
        simulator: SimulatorProtocol,
        evaluator: EvaluatorProtocol,
        rng: random.Random,
        depth: int,
    ) -> float:
        ...


# -------------------------------------------------------------------------
# Heuristic rollout (no simulation — evaluate leaf directly)
# -------------------------------------------------------------------------

class HeuristicRollout:
    """
    Evaluate the leaf position with the evaluator; no random play.

    This is the AlphaZero approach: replace rollouts entirely with the
    value network (or heuristic evaluator for now).
    """

    def rollout(
        self,
        node: MCTSNode,
        simulator: SimulatorProtocol,
        evaluator: EvaluatorProtocol,
        rng: random.Random,
        depth: int,
    ) -> float:
        if simulator.is_terminal(node.state):
            return simulator.terminal_value(node.state, node.player)
        value, _ = evaluator.evaluate(node.state, [])
        return value


# -------------------------------------------------------------------------
# Random rollout
# -------------------------------------------------------------------------

class RandomRollout:
    """
    Play uniformly random actions until terminal or depth limit.

    Classic MCTS simulation phase.  Slow but unbiased.
    """

    def rollout(
        self,
        node: MCTSNode,
        simulator: SimulatorProtocol,
        evaluator: EvaluatorProtocol,
        rng: random.Random,
        depth: int,
    ) -> float:
        state = node.state
        root_player = node.player
        steps = 0

        while steps < depth and not simulator.is_terminal(state):
            actions = simulator.legal_actions(state)
            if not actions:
                break
            action = rng.choice(actions)
            state = simulator.apply_action(state, action)
            steps += 1

        if simulator.is_terminal(state):
            return simulator.terminal_value(state, root_player)

        # Depth limit reached: evaluate with heuristic
        value, _ = evaluator.evaluate(state, [])
        return value


# -------------------------------------------------------------------------
# Greedy rollout
# -------------------------------------------------------------------------

class GreedyRollout:
    """
    Always choose the action whose successor state has the highest
    heuristic value.  More expensive than RandomRollout but often stronger.
    """

    def rollout(
        self,
        node: MCTSNode,
        simulator: SimulatorProtocol,
        evaluator: EvaluatorProtocol,
        rng: random.Random,
        depth: int,
    ) -> float:
        state = node.state
        root_player = node.player
        steps = 0

        while steps < depth and not simulator.is_terminal(state):
            actions = simulator.legal_actions(state)
            if not actions:
                break
            # Evaluate each successor
            best_val = -1.0
            best_action: MCTSAction | None = None
            for action in actions:
                succ = simulator.apply_action(state, action)
                v, _ = evaluator.evaluate(succ, [])
                # Negate if player changes
                if succ.current_player != root_player:
                    v = 1.0 - v
                if v > best_val:
                    best_val = v
                    best_action = action
            if best_action is None:
                break
            state = simulator.apply_action(state, best_action)
            steps += 1

        if simulator.is_terminal(state):
            return simulator.terminal_value(state, root_player)
        value, _ = evaluator.evaluate(state, [])
        return value


# -------------------------------------------------------------------------
# Depth-limited rollout
# -------------------------------------------------------------------------

class DepthLimitedRollout:
    """
    Random for N steps then evaluate with the heuristic.
    Balances speed (random) and accuracy (evaluation at leaf).
    """

    def rollout(
        self,
        node: MCTSNode,
        simulator: SimulatorProtocol,
        evaluator: EvaluatorProtocol,
        rng: random.Random,
        depth: int,
    ) -> float:
        state = node.state
        root_player = node.player
        steps = 0

        while steps < depth and not simulator.is_terminal(state):
            actions = simulator.legal_actions(state)
            if not actions:
                break
            state = simulator.apply_action(state, rng.choice(actions))
            steps += 1

        if simulator.is_terminal(state):
            return simulator.terminal_value(state, root_player)

        value, _ = evaluator.evaluate(state, [])
        # Adjust perspective
        if state.current_player != root_player:
            value = 1.0 - value
        return value


# -------------------------------------------------------------------------
# Factory
# -------------------------------------------------------------------------

def make_rollout(name: str, depth: int = 10) -> RolloutBase:
    from src.mcts.config import RolloutPolicy
    mapping = {
        RolloutPolicy.HEURISTIC:     HeuristicRollout,
        RolloutPolicy.RANDOM:        RandomRollout,
        RolloutPolicy.GREEDY:        GreedyRollout,
        RolloutPolicy.DEPTH_LIMITED: DepthLimitedRollout,
    }
    key = RolloutPolicy(name) if isinstance(name, str) else name
    cls = mapping.get(key)
    if cls is None:
        raise ValueError(f"Unknown rollout policy: {name!r}")
    return cls()
