"""
Archetype detection.

Infers deck archetype purely from card data — no hardcoded deck names.
Returns a ranked list of ArchetypeHypothesis with confidence scores.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from src.decks.curves import CurveReport
from src.decks.metrics import DeckMetrics


class ArchetypeHypothesis(BaseModel):
    """A single archetype candidate with confidence."""

    model_config = ConfigDict(frozen=True)

    archetype: str          # e.g. "Aggro", "Control", "Combo"
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: tuple[str, ...]


class ArchetypeReport(BaseModel):
    """Full archetype detection output."""

    model_config = ConfigDict(frozen=True)

    primary_archetype: str
    secondary_archetype: str | None
    hypotheses: tuple[ArchetypeHypothesis, ...]
    prize_model: str        # "single-prize" | "multi-prize" | "mixed"
    explanation: str


# Prize model thresholds
_MULTI_PRIZE_THRESHOLD = 0.4   # >40% of Pokémon are rule-box → multi-prize


def _prize_model(metrics: DeckMetrics) -> str:
    if metrics.pokemon_count == 0:
        return "unknown"
    ratio = metrics.rule_box_count / metrics.pokemon_count
    if ratio >= _MULTI_PRIZE_THRESHOLD:
        return "multi-prize"
    if ratio <= 0.1:
        return "single-prize"
    return "mixed"


def _score_archetype(
    archetype: str,
    metrics: DeckMetrics,
    curves: CurveReport,
) -> tuple[float, list[str]]:
    """Return (confidence 0-1, evidence list) for an archetype."""
    score = 0.0
    evidence: list[str] = []

    N = 60

    if archetype == "Aggro":
        if curves.speed_rating in ("very-fast", "fast"):
            score += 0.35
            evidence.append(f"Speed rating: {curves.speed_rating}")
        if metrics.energy_count >= 15:
            score += 0.2
            evidence.append(f"High energy count ({metrics.energy_count})")
        if metrics.avg_attack_cost <= 2.0:
            score += 0.2
            evidence.append(f"Low avg attack cost ({metrics.avg_attack_cost})")
        if curves.evolution_depth == 0:
            score += 0.15
            evidence.append("Basic-only attackers")
        if metrics.disruption_score < 5:
            score += 0.1
            evidence.append("Low disruption (all-in aggro)")

    elif archetype == "Control":
        if metrics.disruption_score >= 10:
            score += 0.3
            evidence.append(f"High disruption ({metrics.disruption_score} effects)")
        if metrics.supporter_count >= 12:
            score += 0.25
            evidence.append(f"High supporter count ({metrics.supporter_count})")
        if curves.speed_rating in ("slow", "very-slow"):
            score += 0.2
            evidence.append(f"Slow setup ({curves.speed_rating})")
        if metrics.healing_score >= 5:
            score += 0.15
            evidence.append(f"Healing present ({metrics.healing_score})")
        if metrics.stadium_count >= 3:
            score += 0.1
            evidence.append(f"Multiple stadiums ({metrics.stadium_count})")

    elif archetype == "Combo":
        if metrics.draw_power >= 14:
            score += 0.3
            evidence.append(f"High draw power ({metrics.draw_power})")
        if metrics.search_power >= 10:
            score += 0.25
            evidence.append(f"High search ({metrics.search_power})")
        if curves.evolution_depth >= 2:
            score += 0.2
            evidence.append("Stage 2 combo lines")
        if metrics.energy_acceleration >= 4:
            score += 0.15
            evidence.append(f"Energy acceleration ({metrics.energy_acceleration})")
        if metrics.energy_count <= 8:
            score += 0.1
            evidence.append("Low energy (relies on acceleration)")

    elif archetype == "Midrange":
        # Balanced: moderate everything
        balance = 1.0 - abs(metrics.pokemon_count - 18) / 18
        score += balance * 0.25
        if balance > 0.5:
            evidence.append(f"Balanced Pokémon count ({metrics.pokemon_count})")
        if curves.evolution_depth == 1:
            score += 0.2
            evidence.append("Stage 1 attackers")
        if 10 <= metrics.energy_count <= 16:
            score += 0.2
            evidence.append(f"Moderate energy ({metrics.energy_count})")
        if metrics.trainer_count >= 20:
            score += 0.15
            evidence.append(f"Good trainer support ({metrics.trainer_count})")

    elif archetype == "Stall":
        if metrics.healing_score >= 8:
            score += 0.35
            evidence.append(f"Heavy healing ({metrics.healing_score})")
        if metrics.switch_count >= 6:
            score += 0.2
            evidence.append(f"High switch count ({metrics.switch_count})")
        if metrics.disruption_score >= 8:
            score += 0.2
            evidence.append(f"Disruption ({metrics.disruption_score})")
        if metrics.max_damage < 80:
            score += 0.15
            evidence.append(f"Low max damage ({metrics.max_damage})")
        if metrics.pokemon_count <= 12:
            score += 0.1
            evidence.append(f"Few Pokémon ({metrics.pokemon_count})")

    elif archetype == "Mill":
        if metrics.disruption_score >= 8:
            score += 0.3
            evidence.append(f"High disruption ({metrics.disruption_score})")
        if metrics.supporter_count >= 10:
            score += 0.2
            evidence.append(f"Supporter-heavy ({metrics.supporter_count})")
        if metrics.pokemon_count <= 10:
            score += 0.25
            evidence.append(f"Minimal Pokémon ({metrics.pokemon_count})")

    elif archetype == "Energy Ramp":
        if metrics.energy_acceleration >= 6:
            score += 0.4
            evidence.append(f"High energy acceleration ({metrics.energy_acceleration})")
        if metrics.energy_count >= 16:
            score += 0.25
            evidence.append(f"High energy count ({metrics.energy_count})")
        if metrics.special_energy_count >= 6:
            score += 0.2
            evidence.append(f"Special energy ({metrics.special_energy_count})")
        if metrics.avg_attack_cost >= 3:
            score += 0.15
            evidence.append(f"High attack cost ({metrics.avg_attack_cost}) — needs ramp")

    elif archetype == "Toolbox":
        if metrics.unique_pokemon_names >= 8:
            score += 0.35
            evidence.append(f"Many different Pokémon ({metrics.unique_pokemon_names})")
        if metrics.search_power >= 10:
            score += 0.25
            evidence.append(f"Heavy search ({metrics.search_power})")
        if metrics.tool_count >= 4:
            score += 0.2
            evidence.append(f"Multiple tools ({metrics.tool_count})")
        if metrics.stage2_count == 0 and metrics.stage1_count >= 3:
            score += 0.2
            evidence.append("Variety of Stage 1s")

    elif archetype == "Single Prize":
        prize_model = _prize_model(metrics)
        if prize_model == "single-prize":
            score += 0.5
            evidence.append("Primarily single-prize Pokémon")
        if metrics.basic_pokemon_count >= 12:
            score += 0.2
            evidence.append(f"Basic-heavy ({metrics.basic_pokemon_count})")
        if curves.speed_rating in ("very-fast", "fast"):
            score += 0.2
            evidence.append(f"Fast speed ({curves.speed_rating})")
        if metrics.avg_damage >= 80:
            score += 0.1
            evidence.append(f"Consistent damage ({metrics.avg_damage})")

    elif archetype == "Multi Prize":
        prize_model = _prize_model(metrics)
        if prize_model == "multi-prize":
            score += 0.5
            evidence.append("Primarily multi-prize (ex/V) Pokémon")
        if metrics.max_damage >= 200:
            score += 0.2
            evidence.append(f"High damage ceiling ({metrics.max_damage})")
        if metrics.energy_acceleration >= 3:
            score += 0.15
            evidence.append("Energy acceleration to power big attacks")
        if curves.evolution_depth >= 1:
            score += 0.15
            evidence.append("Evolution-based powerhouses")

    elif archetype == "Hybrid":
        # Catch-all — check if nothing dominates
        score += 0.1
        evidence.append("Mixed strategy elements")

    return round(max(0.0, min(1.0, score)), 3), evidence


_ALL_ARCHETYPES = [
    "Aggro", "Control", "Combo", "Midrange", "Stall",
    "Mill", "Energy Ramp", "Toolbox", "Single Prize", "Multi Prize", "Hybrid",
]


def detect_archetype(metrics: DeckMetrics, curves: CurveReport) -> ArchetypeReport:
    hypotheses: list[ArchetypeHypothesis] = []
    for arch in _ALL_ARCHETYPES:
        conf, evid = _score_archetype(arch, metrics, curves)
        hypotheses.append(ArchetypeHypothesis(
            archetype=arch,
            confidence=conf,
            evidence=tuple(evid),
        ))

    hypotheses.sort(key=lambda h: -h.confidence)
    prize_model = _prize_model(metrics)

    primary = hypotheses[0].archetype if hypotheses else "Unknown"
    secondary = hypotheses[1].archetype if len(hypotheses) > 1 and hypotheses[1].confidence >= 0.2 else None

    explanation = (
        f"This deck is primarily identified as {primary} "
        f"(confidence {hypotheses[0].confidence:.0%})"
    )
    if secondary:
        explanation += f" with {secondary} elements (confidence {hypotheses[1].confidence:.0%})"
    explanation += f". Prize model: {prize_model}."

    return ArchetypeReport(
        primary_archetype=primary,
        secondary_archetype=secondary,
        hypotheses=tuple(hypotheses),
        prize_model=prize_model,
        explanation=explanation,
    )
