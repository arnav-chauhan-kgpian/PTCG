"""
CandidateDeck — a scored, annotated deck candidate.
BuildResult — the final output from DeckBuilder.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.deck_builder.scoring import CandidateScore
from src.decks.models import Deck
from src.decks.reports import DeckReport


@dataclass
class CandidateDeck:
    """A deck with its full analysis and ranking metadata."""

    deck: Deck
    score: CandidateScore
    report: DeckReport
    rank: int = 0

    # Generation provenance
    generation_strategy: str = ""          # "greedy", "hill_climbing", etc.
    seed_cards: list[str] = field(default_factory=list)

    # Card-level justifications
    card_selection_reasons: dict[str, str] = field(default_factory=dict)

    # Suggested upgrades
    suggested_upgrades: list[str] = field(default_factory=list)

    def __lt__(self, other: CandidateDeck) -> bool:
        return self.score.total < other.score.total

    def summary_line(self) -> str:
        return (
            f"[#{self.rank}] {self.deck.name} "
            f"score={self.score.total:.1f} "
            f"archetype={self.report.archetype.primary_archetype} "
            f"legal={self.score.is_legal} "
            f"strategy={self.generation_strategy}"
        )


@dataclass
class BuildResult:
    """Top-K ranked candidates from one DeckBuilder.build() call."""

    request_summary: str
    candidates: list[CandidateDeck]

    @property
    def best(self) -> CandidateDeck | None:
        return self.candidates[0] if self.candidates else None

    def ranked(self) -> list[CandidateDeck]:
        return sorted(self.candidates, key=lambda c: -c.score.total)


def rank_candidates(candidates: list[CandidateDeck]) -> list[CandidateDeck]:
    """Sort candidates by score and assign rank numbers."""
    sorted_cands = sorted(candidates, key=lambda c: -c.score.total)
    for i, c in enumerate(sorted_cands, start=1):
        c.rank = i
    return sorted_cands
