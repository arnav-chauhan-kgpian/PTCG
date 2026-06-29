"""
DeckReport assembly — combines all analysis sections into one structured report.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from src.decks.archetypes import ArchetypeReport
from src.decks.consistency import ConsistencyReport
from src.decks.curves import CurveReport
from src.decks.matchup import MatchupReport
from src.decks.metrics import DeckMetrics
from src.decks.synergy import SynergyReport
from src.decks.validators import ValidationReport
from src.decks.win_conditions import WinConditionReport


class DeckReport(BaseModel):
    """Complete analysis report for a 60-card deck."""

    model_config = ConfigDict(frozen=True)

    # --- Identity ---
    deck_name: str
    is_legal: bool

    # --- Validation ---
    validation: ValidationReport

    # --- Sub-reports ---
    metrics: DeckMetrics
    curves: CurveReport
    consistency: ConsistencyReport
    synergy: SynergyReport
    archetype: ArchetypeReport
    win_conditions: WinConditionReport
    matchup: MatchupReport

    # --- Human-readable summary ---
    strengths: tuple[str, ...]
    weaknesses: tuple[str, ...]
    risk_factors: tuple[str, ...]
    missing_cards: tuple[str, ...]
    replacement_suggestions: tuple[tuple[str, str], ...]   # (current, suggested)
    consistency_notes: tuple[str, ...]
    energy_notes: tuple[str, ...]
    overall_summary: str

    # --- Graph statistics ---
    graph_stats: dict[str, int]


def _derive_strengths(
    metrics: DeckMetrics,
    curves: CurveReport,
    consistency: ConsistencyReport,
    synergy: SynergyReport,
    archetype: ArchetypeReport,
) -> list[str]:
    strengths: list[str] = []
    if consistency.consistency_score >= 70:
        strengths.append(f"High consistency score ({consistency.consistency_score:.0f}/100)")
    if curves.speed_rating in ("very-fast", "fast"):
        strengths.append(f"Fast setup ({curves.speed_rating})")
    if metrics.draw_power >= 14:
        strengths.append(f"Strong draw engine ({metrics.draw_power} draw effects)")
    if metrics.max_damage >= 200:
        strengths.append(f"Explosive damage ceiling ({metrics.max_damage})")
    if metrics.energy_acceleration >= 5:
        strengths.append(f"Energy acceleration ({metrics.energy_acceleration} accelerators)")
    if synergy.engine_cohesion >= 70:
        strengths.append(f"Cohesive engine ({synergy.engine_cohesion:.0f}% cohesion)")
    if metrics.recovery_score >= 6:
        strengths.append(f"Good recovery options ({metrics.recovery_score} recovery cards)")
    if metrics.disruption_score >= 10:
        strengths.append(f"Disruption package ({metrics.disruption_score} effects)")
    if not strengths:
        strengths.append("Balanced all-around deck")
    return strengths


def _derive_weaknesses(
    metrics: DeckMetrics,
    curves: CurveReport,
    consistency: ConsistencyReport,
    synergy: SynergyReport,
) -> list[str]:
    weaknesses: list[str] = []
    if consistency.consistency_score < 40:
        weaknesses.append(f"Low consistency ({consistency.consistency_score:.0f}/100)")
    if curves.speed_rating in ("slow", "very-slow"):
        weaknesses.append(f"Slow setup ({curves.speed_rating})")
    if metrics.basic_pokemon_count <= 4:
        weaknesses.append(f"Few Basic Pokémon ({metrics.basic_pokemon_count}) — high mulligan risk")
    if metrics.draw_power < 6:
        weaknesses.append(f"Weak draw engine ({metrics.draw_power} draw effects)")
    if len(synergy.orphan_cards) >= 5:
        weaknesses.append(f"{len(synergy.orphan_cards)} orphan cards with no synergy")
    if metrics.energy_count > 20:
        weaknesses.append(f"Energy-heavy ({metrics.energy_count}) — fewer trainer options")
    if metrics.prize_liability_score >= 0.6:
        weaknesses.append("High prize liability — giving up 2 prizes per KO frequently")
    if metrics.rule_box_count > 0 and metrics.basic_pokemon_count < 6:
        weaknesses.append("Multi-prize Pokémon with limited basic backup")
    if not weaknesses:
        weaknesses.append("No critical structural weaknesses identified")
    return weaknesses


def _derive_risk_factors(
    metrics: DeckMetrics,
    curves: CurveReport,
    consistency: ConsistencyReport,
) -> list[str]:
    risks: list[str] = []
    if consistency.expected_mulligans >= 1.0:
        risks.append(f"Expected {consistency.expected_mulligans:.1f} mulligans per game")
    if curves.evolution_depth >= 2 and metrics.search_power < 8:
        risks.append("Stage 2 lines without sufficient search — inconsistent setup")
    if metrics.energy_count < 8 and metrics.energy_acceleration < 3:
        risks.append("Low energy with no acceleration — risk of energy drought")
    if metrics.supporter_count < 8:
        risks.append(f"Few supporters ({metrics.supporter_count}) — limited hand refresh")
    if metrics.stage2_count > 0 and metrics.basic_pokemon_count < 4:
        risks.append("Stage 2 lines with very few basics — prizing a basic strands evolutions")
    return risks


def _derive_energy_notes(metrics: DeckMetrics, curves: CurveReport) -> list[str]:
    notes: list[str] = []
    notes.append(f"Energy count: {metrics.energy_count} ({metrics.basic_energy_count} basic, {metrics.special_energy_count} special)")
    notes.append(f"Average attack cost: {metrics.avg_attack_cost:.1f} energy tokens")
    notes.append(f"Energy curve skew: {curves.energy_cost_skew}")
    if metrics.energy_acceleration >= 3:
        notes.append(f"Energy acceleration present ({metrics.energy_acceleration} cards)")
    if metrics.special_energy_count >= 4:
        notes.append(f"Special energy package ({metrics.special_energy_count} cards) adds flexibility")
    return notes


def _derive_consistency_notes(
    consistency: ConsistencyReport,
    metrics: DeckMetrics,
) -> list[str]:
    notes: list[str] = []
    notes.append(f"Opening basic probability: {consistency.p_opening_basic:.1%}")
    notes.append(f"Expected mulligans: {consistency.expected_mulligans:.1f} per game")
    notes.append(f"Draw density: {consistency.draw_density:.1%} of deck ({metrics.draw_power} cards)")
    notes.append(f"Search density: {consistency.search_density:.1%} of deck ({metrics.search_power} cards)")
    notes.append(f"Overall consistency grade: {consistency.consistency_grade}")
    return notes


def assemble_report(
    deck_name: str,
    validation: ValidationReport,
    metrics: DeckMetrics,
    curves: CurveReport,
    consistency: ConsistencyReport,
    synergy: SynergyReport,
    archetype: ArchetypeReport,
    win_conditions: WinConditionReport,
    matchup: MatchupReport,
    graph_stats: dict[str, int] | None = None,
) -> DeckReport:
    strengths = _derive_strengths(metrics, curves, consistency, synergy, archetype)
    weaknesses = _derive_weaknesses(metrics, curves, consistency, synergy)
    risks = _derive_risk_factors(metrics, curves, consistency)
    energy_notes = _derive_energy_notes(metrics, curves)
    consistency_notes = _derive_consistency_notes(consistency, metrics)

    missing_cards = list(synergy.missing_support[:5])

    # Replacement suggestions: orphan cards → missing support pairs
    replacements: list[tuple[str, str]] = []
    for orphan, suggested in zip(synergy.orphan_cards, synergy.missing_support):
        replacements.append((orphan, suggested))

    overall_summary = (
        f"'{deck_name}' is a {archetype.primary_archetype} deck "
        f"({'legal' if validation.is_legal else 'ILLEGAL'}). "
        f"Consistency: {consistency.consistency_grade}, "
        f"Speed: {curves.speed_rating}, "
        f"Synergy: {synergy.synergy_score:.0f}/100. "
        f"Primary win condition: {win_conditions.primary_win_condition[:60]}."
    )

    return DeckReport(
        deck_name=deck_name,
        is_legal=validation.is_legal,
        validation=validation,
        metrics=metrics,
        curves=curves,
        consistency=consistency,
        synergy=synergy,
        archetype=archetype,
        win_conditions=win_conditions,
        matchup=matchup,
        strengths=tuple(strengths),
        weaknesses=tuple(weaknesses),
        risk_factors=tuple(risks),
        missing_cards=tuple(missing_cards),
        replacement_suggestions=tuple(replacements),
        consistency_notes=tuple(consistency_notes),
        energy_notes=tuple(energy_notes),
        overall_summary=overall_summary,
        graph_stats=graph_stats or {},
    )
