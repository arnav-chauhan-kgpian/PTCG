"""
Training target construction — turn raw MCTS output into supervised
training tuples for the joint network.

Given the visit counts from one MCTS root expansion plus the eventual
terminal value of the game, this module produces:

    policy_target : softmax-normalised distribution over action_map
    value_target  : in [0, 1] from the perspective of the moving player

Temperature schedules are supported so early moves can use a flatter
(more exploratory) policy target while late-game moves sharpen.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.mcts.node import MCTSAction

# -------------------------------------------------------------------------
# Policy targets from visit counts
# -------------------------------------------------------------------------

def visit_counts_to_policy(
    visit_counts: dict[MCTSAction, int],
    temperature: float = 1.0,
) -> dict[MCTSAction, float]:
    """
    Convert MCTS visit counts to a probability distribution.

    Temperature controls sharpening:
        τ → 0 : argmax (one-hot on most-visited action)
        τ = 1 : N / sum(N) (the visit-count distribution)
        τ > 1 : flatter distribution
    """
    if not visit_counts:
        return {}

    counts = {a: max(n, 0) for a, n in visit_counts.items()}
    total = sum(counts.values())
    if total == 0:
        n = len(counts)
        return dict.fromkeys(counts, 1.0 / n)

    if temperature <= 1e-3:
        # Argmax
        best = max(counts, key=lambda a: counts[a])
        return {a: (1.0 if a == best else 0.0) for a in counts}

    if temperature == 1.0:
        return {a: c / total for a, c in counts.items()}

    powed = {a: (c ** (1.0 / temperature)) for a, c in counts.items()}
    s = sum(powed.values()) or 1.0
    return {a: v / s for a, v in powed.items()}


def policy_to_vector(
    policy: dict[MCTSAction, float],
    action_map: list[MCTSAction],
) -> list[float]:
    """Project a sparse policy onto a fixed-length vector indexed by action_map."""
    vec = [0.0] * len(action_map)
    for action, p in policy.items():
        try:
            idx = action_map.index(action)
            vec[idx] = p
        except ValueError:
            pass  # action not in fixed action map — drop
    s = sum(vec)
    if s > 0:
        vec = [v / s for v in vec]
    return vec


# -------------------------------------------------------------------------
# Value targets from terminal outcome
# -------------------------------------------------------------------------

def outcome_to_value_target(
    terminal_value: float,
    move_player: int,
    winner: int | None,
) -> float:
    """
    Compute the value target for a single training sample.

    Conventions
    -----------
    terminal_value : float in [0, 1]
        Final reward for player 0 (1.0 = P0 wins, 0.0 = P1 wins, 0.5 = draw).
    move_player : int
        Player who made the move that produced this training sample.
    winner : Optional[int]
        Winning player id, or None for draw / unknown.

    Returns the value target in [0, 1] from the move_player's perspective.
    """
    if winner is None:
        # Draw or unfinished — value flips to move_player's perspective
        return terminal_value if move_player == 0 else 1.0 - terminal_value
    if winner == move_player:
        return 1.0
    return 0.0


# -------------------------------------------------------------------------
# Temperature schedules
# -------------------------------------------------------------------------

@dataclass(frozen=True)
class TemperatureSchedule:
    """
    Linear-then-constant temperature schedule.

    Default:
        moves 0 .. early_moves-1     → temperature_high (exploratory)
        moves >= early_moves         → temperature_low (sharp)
    """
    early_moves: int = 15
    temperature_high: float = 1.0
    temperature_low: float = 0.0

    def temperature_for(self, move_number: int) -> float:
        if move_number < self.early_moves:
            return self.temperature_high
        return self.temperature_low


# -------------------------------------------------------------------------
# Sample container
# -------------------------------------------------------------------------

@dataclass(frozen=True)
class TrainingSample:
    """One (state_features, policy_target, value_target) tuple."""

    state_features: tuple[float, ...]
    policy_target: tuple[float, ...]
    value_target: float
    move_player: int = 0
    move_number: int = 0

    def to_dict(self) -> dict:
        return {
            "state_features": list(self.state_features),
            "policy_target": list(self.policy_target),
            "value_target": self.value_target,
            "move_player": self.move_player,
            "move_number": self.move_number,
        }

    @classmethod
    def from_dict(cls, data: dict) -> TrainingSample:
        return cls(
            state_features=tuple(data["state_features"]),
            policy_target=tuple(data["policy_target"]),
            value_target=float(data["value_target"]),
            move_player=int(data.get("move_player", 0)),
            move_number=int(data.get("move_number", 0)),
        )
