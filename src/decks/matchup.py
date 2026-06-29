"""
Matchup estimation.

Uses type matchups and strategy profile to estimate performance
against broad strategy families. No simulation required.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from src.decks.archetypes import ArchetypeReport
from src.decks.curves import CurveReport
from src.decks.metrics import DeckMetrics


class MatchupEstimate(BaseModel):
    """Performance estimate against one strategy family."""

    model_config = ConfigDict(frozen=True)

    opponent_strategy: str
    rating: str         # "favored" | "even" | "unfavored" | "heavily-favored" | "heavily-unfavored"
    score: float        # -1.0 (worst) to +1.0 (best)
    explanation: str


class MatchupReport(BaseModel):
    """Full matchup tendency report."""

    model_config = ConfigDict(frozen=True)

    matchups: tuple[MatchupEstimate, ...]
    best_matchup: str
    worst_matchup: str
    overall_matchup_score: float   # average across all


_OPPONENT_STRATEGIES = [
    "Fast Aggro",
    "Control",
    "Energy Ramp",
    "Evolution Decks",
    "Single Prize",
    "Multi Prize",
    "Stall",
    "Mill",
]


def _rate(score: float) -> str:
    if score >= 0.6:
        return "heavily-favored"
    if score >= 0.25:
        return "favored"
    if score >= -0.25:
        return "even"
    if score >= -0.6:
        return "unfavored"
    return "heavily-unfavored"


def _weakness_coverage(metrics: DeckMetrics) -> float:
    """Fraction of opponent types for which we have resistance."""
    # Simple proxy: if resistance_distribution is non-empty → some protection
    return min(1.0, len(metrics.resistance_distribution) * 0.25)


def _estimate_matchup(
    opponent: str,
    metrics: DeckMetrics,
    curves: CurveReport,
    archetype: ArchetypeReport,
) -> MatchupEstimate:
    score = 0.0
    reasons: list[str] = []
    arch = archetype.primary_archetype

    if opponent == "Fast Aggro":
        # We beat fast aggro if we're fast too, or if we control / stall
        if curves.speed_rating in ("very-fast", "fast"):
            score += 0.3
            reasons.append("Our speed matches theirs")
        if metrics.healing_score >= 5:
            score += 0.25
            reasons.append("Healing extends our Pokémon's lifespan")
        if arch in ("Control", "Stall"):
            score += 0.2
            reasons.append("Control tools slow aggro down")
        if curves.evolution_depth >= 2:
            score -= 0.3
            reasons.append("Stage 2 setup is too slow vs fast aggro")
        if metrics.basic_pokemon_count <= 4:
            score -= 0.2
            reasons.append("Few basics; risk of mulligans against early aggro")

    elif opponent == "Control":
        if metrics.draw_power >= 14:
            score += 0.3
            reasons.append("High draw power fights through hand disruption")
        if metrics.recovery_score >= 6:
            score += 0.25
            reasons.append("Recovery lets us rebuild after disruption")
        if arch == "Aggro":
            score += 0.2
            reasons.append("Fast pressure prevents control from setting up")
        if arch == "Control":
            score -= 0.1
            reasons.append("Mirror match — slight variance")
        if metrics.disruption_score >= 8:
            score += 0.15
            reasons.append("We can out-disrupt the control player")

    elif opponent == "Energy Ramp":
        if metrics.disruption_score >= 10:
            score += 0.35
            reasons.append("Disruption prevents energy accumulation")
        if curves.speed_rating in ("very-fast", "fast"):
            score += 0.3
            reasons.append("Close game before ramp comes online")
        if arch == "Energy Ramp":
            score -= 0.2
            reasons.append("Mirror depends on who ramps faster")
        if metrics.energy_count <= 8:
            score += 0.1
            reasons.append("Lean energy; opponent can't deny what we don't rely on")

    elif opponent == "Evolution Decks":
        if curves.speed_rating in ("very-fast", "fast"):
            score += 0.3
            reasons.append("Attack before evolutions complete")
        if metrics.disruption_score >= 8:
            score += 0.25
            reasons.append("Disruption slows evolution chains")
        if curves.evolution_depth >= 2:
            score -= 0.15
            reasons.append("We also need setup time — mirror vulnerability")
        if arch == "Combo":
            score += 0.15
            reasons.append("Combo decks often out-power slow evolution builds")

    elif opponent == "Single Prize":
        if archetype.prize_model == "multi-prize":
            score -= 0.35
            reasons.append("We give up 2 prizes per KO while they give 1 — prize trade disadvantage")
        elif archetype.prize_model == "single-prize":
            score += 0.2
            reasons.append("Prize trade parity")
        if metrics.max_damage >= 150:
            score += 0.2
            reasons.append("High damage enables OHKO of small basics")
        if metrics.avg_damage >= 100:
            score += 0.15
            reasons.append("Consistent damage clears single-prize targets")

    elif opponent == "Multi Prize":
        if archetype.prize_model == "single-prize":
            score += 0.3
            reasons.append("We take 2 prizes per KO while giving 1 — prize trade advantage")
        if metrics.disruption_score >= 8:
            score += 0.2
            reasons.append("Disruption prevents multi-prize setup")
        if metrics.max_damage < 120:
            score -= 0.2
            reasons.append("Low damage ceiling struggles to KO bulky multi-prize cards")
        if arch == "Control":
            score += 0.15
            reasons.append("Control limits the explosive turns big attackers need")

    elif opponent == "Stall":
        if metrics.draw_power >= 14:
            score += 0.3
            reasons.append("Draw power lets us cycle through stall walls")
        if metrics.max_damage >= 150:
            score += 0.25
            reasons.append("High damage can overwhelm healing")
        if metrics.energy_acceleration >= 5:
            score += 0.2
            reasons.append("Energy ramp powers through stall barriers")
        if arch == "Stall":
            score -= 0.3
            reasons.append("Mirror stall results in very long games with coin-flip outcomes")
        if metrics.avg_damage <= 50:
            score -= 0.25
            reasons.append("Low damage cannot overcome stall healing")

    elif opponent == "Mill":
        if metrics.recovery_score >= 8:
            score += 0.4
            reasons.append("High recovery negates mill progress")
        if arch in ("Aggro", "Single Prize"):
            score += 0.3
            reasons.append("Fast pressure closes before mill completes")
        if metrics.draw_power >= 15:
            score -= 0.15
            reasons.append("Heavy draw accelerates our own deck-out")
        if metrics.pokemon_count <= 10:
            score -= 0.25
            reasons.append("Few Pokémon — mill removes our attackers quickly")

    explanation = f"vs {opponent}: " + ("; ".join(reasons) if reasons else "neutral matchup")

    return MatchupEstimate(
        opponent_strategy=opponent,
        rating=_rate(score),
        score=round(max(-1.0, min(1.0, score)), 3),
        explanation=explanation,
    )


def compute_matchups(
    metrics: DeckMetrics,
    curves: CurveReport,
    archetype: ArchetypeReport,
) -> MatchupReport:
    matchups = [
        _estimate_matchup(opp, metrics, curves, archetype)
        for opp in _OPPONENT_STRATEGIES
    ]
    matchups.sort(key=lambda m: -m.score)

    best = matchups[0].opponent_strategy if matchups else "N/A"
    worst = matchups[-1].opponent_strategy if matchups else "N/A"
    avg_score = sum(m.score for m in matchups) / len(matchups) if matchups else 0.0

    return MatchupReport(
        matchups=tuple(matchups),
        best_matchup=best,
        worst_matchup=worst,
        overall_matchup_score=round(avg_score, 3),
    )
