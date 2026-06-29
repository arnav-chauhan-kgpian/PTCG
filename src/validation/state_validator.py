"""
StateValidator — structural consistency checks on a single GameState.

Wraps the existing ``src.game_state.validators.validate_state`` plus
simulator-specific invariants (active+bench disjoint, prizes counted).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from src.game_state.validators import validate_state as _gs_validate

if TYPE_CHECKING:
    from src.game_state.state import GameState


@dataclass
class StateIssue:
    code: str
    message: str
    severity: str = "error"


@dataclass
class StateValidationResult:
    issues: list[StateIssue] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not any(i.severity == "error" for i in self.issues)

    def to_dict(self) -> dict:
        return {
            "is_valid": self.is_valid,
            "issues": [vars(i) for i in self.issues],
        }


class StateValidator:
    """Validates one GameState against game-state and simulator invariants."""

    def validate(self, state: GameState) -> StateValidationResult:
        result = StateValidationResult()
        # Phase-7 structural checks
        gs_report = _gs_validate(state)
        for issue in gs_report.issues:
            result.issues.append(StateIssue(
                code=issue.code, message=issue.message, severity=issue.severity,
            ))
        # Simulator-specific
        for pidx, p in enumerate(state.players):
            if p.active and p.active in p.bench:
                result.issues.append(StateIssue(
                    code="ACTIVE_AND_BENCH",
                    message=f"player {pidx} active also on bench",
                ))
            if p.prizes_remaining > 6:
                result.issues.append(StateIssue(
                    code="PRIZES_OVER_SIX",
                    message=f"player {pidx} prizes_remaining={p.prizes_remaining}",
                ))
        return result
