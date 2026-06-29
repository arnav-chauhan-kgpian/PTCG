"""
Deck Intelligence Engine — public API.

Usage::

    from src.decks import DeckAnalyzer, parse_deck, DeckReport
    from src.decks import exports

    analyzer = DeckAnalyzer(graph)
    report = analyzer.analyze(deck)
    print(exports.to_terminal(report))
"""

from src.decks import exports
from src.decks.analyzer import DeckAnalyzer, parse_deck
from src.decks.archetypes import ArchetypeHypothesis, ArchetypeReport, detect_archetype
from src.decks.consistency import ConsistencyReport, compute_consistency
from src.decks.curves import CurveReport, compute_curves
from src.decks.matchup import MatchupEstimate, MatchupReport, compute_matchups
from src.decks.metrics import DeckMetrics, compute_metrics
from src.decks.models import Deck, DeckSlot
from src.decks.reports import DeckReport, assemble_report
from src.decks.synergy import SynergyReport, compute_synergy
from src.decks.validators import DeckValidator, ValidationIssue, ValidationReport
from src.decks.win_conditions import WinConditionReport, compute_win_conditions

__all__ = [
    # Models
    "Deck",
    "DeckSlot",
    # Validation
    "DeckValidator",
    "ValidationReport",
    "ValidationIssue",
    # Sub-reports
    "DeckMetrics",
    "CurveReport",
    "ConsistencyReport",
    "SynergyReport",
    "ArchetypeReport",
    "ArchetypeHypothesis",
    "WinConditionReport",
    "MatchupReport",
    "MatchupEstimate",
    # Master report
    "DeckReport",
    # Functions
    "compute_metrics",
    "compute_curves",
    "compute_consistency",
    "compute_synergy",
    "detect_archetype",
    "compute_win_conditions",
    "compute_matchups",
    "assemble_report",
    "parse_deck",
    # Analyzer
    "DeckAnalyzer",
    # Exports module
    "exports",
]
