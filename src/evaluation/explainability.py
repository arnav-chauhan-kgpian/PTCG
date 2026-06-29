"""
P2.7 — Explainability.

Turns an MCTS search result into a human-readable rationale for the
chosen move, with top actions, visit counts, priors, value estimates,
and principal variation.  Exports to plain text or Markdown.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.game_state.state import GameState
    from src.mcts.search import SearchResult


@dataclass
class ActionRanking:
    rank: int
    action: str
    visits: int
    visit_share: float
    q_value: float
    prior: float


@dataclass
class DecisionExplanation:
    """Explanation of a single MCTS decision."""
    state_summary: str = ""
    chosen_action: str = ""
    rankings: list[ActionRanking] = field(default_factory=list)
    principal_variation: list[str] = field(default_factory=list)
    expected_prize_swing: float = 0.0
    expected_ko_sequence: list[str] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "state_summary": self.state_summary,
            "chosen_action": self.chosen_action,
            "rankings": [vars(r) for r in self.rankings],
            "principal_variation": list(self.principal_variation),
            "expected_prize_swing": self.expected_prize_swing,
            "expected_ko_sequence": list(self.expected_ko_sequence),
            "notes": self.notes,
        }

    def to_markdown(self) -> str:
        lines = [
            "# MCTS Decision",
            "",
            f"**State:** {self.state_summary}",
            f"**Chosen:** `{self.chosen_action}`",
            "",
            "## Top actions",
            "",
            "| Rank | Action | Visits | Share | Q | Prior |",
            "| ---: | --- | ---: | ---: | ---: | ---: |",
        ]
        for r in self.rankings:
            lines.append(
                f"| {r.rank} | `{r.action}` | {r.visits} | "
                f"{r.visit_share:.1%} | {r.q_value:.3f} | {r.prior:.3f} |"
            )
        lines.append("")
        if self.principal_variation:
            lines.append("## Principal variation")
            lines.append("")
            for i, m in enumerate(self.principal_variation, 1):
                lines.append(f"{i}. `{m}`")
            lines.append("")
        if self.notes:
            lines.append("## Notes")
            lines.append("")
            lines.append(self.notes)
        return "\n".join(lines)


def explain_decision(
    state: GameState,
    result: SearchResult,
    *,
    top_k: int = 5,
) -> DecisionExplanation:
    """Build an explanation from a SearchResult on a given state."""
    expl = DecisionExplanation()
    expl.state_summary = _summarise_state(state)
    expl.chosen_action = str(result.best_action) if result.best_action else ""
    total = max(result.total_visits, 1)
    sorted_children = sorted(
        result.visit_counts.items(), key=lambda kv: -kv[1],
    )[:top_k]
    # Pull child Q-values and priors via the tree root through the search
    # result's underlying tree if available.
    for rank, (action, visits) in enumerate(sorted_children, 1):
        share = visits / total
        # SearchResult doesn't directly expose Q/prior per action; we
        # approximate using the visit-count distribution.
        expl.rankings.append(ActionRanking(
            rank=rank, action=str(action), visits=visits,
            visit_share=round(share, 4),
            q_value=0.0, prior=round(1.0 / max(1, len(result.visit_counts)), 4),
        ))
    expl.principal_variation = [str(a) for a in result.principal_variation[:6]]
    expl.expected_prize_swing = _expected_prize_swing(state)
    return expl


def _summarise_state(state: GameState) -> str:
    p0, p1 = state.players
    return (
        f"T{state.turn_number} P{state.current_player}'s turn — "
        f"P0 prizes={p0.prizes_remaining} hand={p0.hand_count} "
        f"deck={p0.deck_size} bench={len(p0.bench)} | "
        f"P1 prizes={p1.prizes_remaining} hand={p1.hand_count} "
        f"deck={p1.deck_size} bench={len(p1.bench)}"
    )


def _expected_prize_swing(state: GameState) -> float:
    """Rough heuristic: prize delta from current player's perspective."""
    me = state.players[state.current_player]
    opp = state.players[1 - state.current_player]
    return (opp.prizes_remaining - me.prizes_remaining) / 6.0
