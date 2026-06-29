"""
Pre-action legality checks producing structured reports.

Used by tests and debugging tools; the executor itself silently no-ops
on illegal actions for performance reasons.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.game_state.state import GameState
from src.mcts.node import MCTSAction
from src.simulator.legal_actions import legal_actions
from src.simulator.rules import GameRules

if TYPE_CHECKING:
    from src.cards.repository import CardRepository


@dataclass(frozen=True)
class LegalityResult:
    legal: bool
    reason: str = ""

    @classmethod
    def ok(cls) -> LegalityResult:
        return cls(legal=True)

    @classmethod
    def fail(cls, reason: str) -> LegalityResult:
        return cls(legal=False, reason=reason)


def is_legal(
    state: GameState, action: MCTSAction,
    repository: CardRepository, rules: GameRules,
) -> LegalityResult:
    """Check whether *action* is in the legal-action set for *state*."""
    if state.is_terminal:
        return LegalityResult.fail("game is over")
    legal_set = legal_actions(state, repository, rules)
    if action in legal_set:
        return LegalityResult.ok()
    return LegalityResult.fail(
        f"action {action.action_type} not in legal set ({len(legal_set)} legal actions)"
    )
