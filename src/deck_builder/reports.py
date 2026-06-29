"""
BuildReport — per-candidate explanation of why cards were selected.
"""

from __future__ import annotations

from src.deck_builder.candidates import BuildResult, CandidateDeck


def annotate_candidate(
    candidate: CandidateDeck,
    seed_cards: list[str],
    generation_strategy: str,
) -> CandidateDeck:
    """Attach card-level justifications and upgrade suggestions to a candidate."""
    report = candidate.report
    reasons: dict[str, str] = {}

    for slot in candidate.deck.slots:
        card = slot.card
        name = card.name
        # Look up profile
        cid = str(card.card_id)
        profile = None
        try:
            pass
        except Exception:
            pass

        if name in seed_cards:
            reasons[name] = f"Core card (seed): {name}"
        elif name in (c for c in report.win_conditions.core_engine):
            reasons[name] = "Core engine card: high internal synergy"
        elif name in (c for c in report.win_conditions.finishers):
            reasons[name] = "Finisher: identified as primary damage dealer"
        elif name in (c for c in report.synergy.combo_anchors):
            reasons[name] = f"Combo anchor: {report.synergy.internal_edge_count} internal edges"
        else:
            from src.cards.models import EnergyCard, PokemonCard, TrainerCard
            if isinstance(card, PokemonCard):
                reasons[name] = f"Support Pokémon: stage={card.stage.value}"
            elif isinstance(card, TrainerCard):
                effect_preview = card.effect[:60].replace("\n", " ")
                reasons[name] = f"Trainer: {effect_preview}…"
            elif isinstance(card, EnergyCard):
                provides = ", ".join(p.value for p in card.provides)
                reasons[name] = f"Energy ({card.energy_type.value}): provides {provides}"

    # Upgrade suggestions = missing support cards not in deck
    upgrades = list(report.missing_cards[:5])

    candidate.card_selection_reasons.update(reasons)
    candidate.suggested_upgrades = upgrades
    candidate.generation_strategy = generation_strategy
    candidate.seed_cards = list(seed_cards)
    return candidate


def build_result_summary(result: BuildResult) -> str:
    lines = [f"Build Result: {result.request_summary}",
             f"Candidates: {len(result.candidates)}"]
    for c in result.ranked():
        lines.append(f"  {c.summary_line()}")
    return "\n".join(lines)
