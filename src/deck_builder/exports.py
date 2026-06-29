"""
Export deck candidates to multiple formats.

Formats:
  ptcg_live   — Standard Pokémon TCG Live text format
  json        — Full candidate data as JSON
  markdown    — Human-readable Markdown
  csv         — One row per candidate (metrics summary)
  terminal    — Compact terminal view
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

from src.deck_builder.candidates import BuildResult, CandidateDeck
from src.decks.exports import to_markdown as deck_markdown
from src.decks.exports import to_terminal as deck_terminal

# ---------------------------------------------------------------------------
# PTCG Live text format
# ---------------------------------------------------------------------------

def to_ptcg_live(candidate: CandidateDeck) -> str:
    """
    Pokémon TCG Live format:
        Pokémon: N
        4 Charizard ex OBF 125
        ...
        Trainer: N
        4 Professor's Research SVI 189
        ...
        Energy: N
        14 Fire Energy SVE 2

        Total Cards: 60
    """
    from src.cards.models import EnergyCard, PokemonCard, TrainerCard
    pokemon_lines: list[str] = []
    trainer_lines: list[str] = []
    energy_lines: list[str] = []

    for slot in candidate.deck.slots:
        card = slot.card
        expansion = card.expansion.value or "UNK"
        num = card.collection_number
        line = f"{slot.count} {card.name} {expansion} {num}"
        if isinstance(card, PokemonCard):
            pokemon_lines.append(line)
        elif isinstance(card, TrainerCard):
            trainer_lines.append(line)
        elif isinstance(card, EnergyCard):
            energy_lines.append(line)

    sections: list[str] = []
    if pokemon_lines:
        pcount = sum(slot.count for slot in candidate.deck.pokemon_slots())
        sections.append(f"Pokémon: {pcount}")
        sections.extend(sorted(pokemon_lines))
        sections.append("")
    if trainer_lines:
        tcount = sum(slot.count for slot in candidate.deck.trainer_slots())
        sections.append(f"Trainer: {tcount}")
        sections.extend(sorted(trainer_lines))
        sections.append("")
    if energy_lines:
        ecount = sum(slot.count for slot in candidate.deck.energy_slots())
        sections.append(f"Energy: {ecount}")
        sections.extend(sorted(energy_lines))
        sections.append("")

    sections.append(f"Total Cards: {candidate.deck.total_count}")
    return "\n".join(sections)


# ---------------------------------------------------------------------------
# JSON
# ---------------------------------------------------------------------------

def to_json(candidate: CandidateDeck, *, indent: int = 2) -> str:
    data = {
        "rank": candidate.rank,
        "score": candidate.score.total,
        "is_legal": candidate.score.is_legal,
        "archetype": candidate.report.archetype.primary_archetype,
        "generation_strategy": candidate.generation_strategy,
        "seed_cards": candidate.seed_cards,
        "objective_breakdown": candidate.score.objective_breakdown,
        "deck_name": candidate.deck.name,
        "strengths": list(candidate.report.strengths),
        "weaknesses": list(candidate.report.weaknesses),
        "card_selection_reasons": candidate.card_selection_reasons,
        "suggested_upgrades": candidate.suggested_upgrades,
        "decklist": {
            slot.name: slot.count
            for slot in candidate.deck.slots
        },
        "ptcg_live": to_ptcg_live(candidate),
        "consistency": {
            "score": candidate.report.consistency.consistency_score,
            "grade": candidate.report.consistency.consistency_grade,
            "p_opening_basic": candidate.report.consistency.p_opening_basic,
        },
    }
    return json.dumps(data, indent=indent, ensure_ascii=False)


def to_json_build_result(result: BuildResult, *, indent: int = 2) -> str:
    return json.dumps({
        "request_summary": result.request_summary,
        "candidate_count": len(result.candidates),
        "candidates": [json.loads(to_json(c)) for c in result.ranked()],
    }, indent=indent, ensure_ascii=False)


def write_json(candidate: CandidateDeck, path: str | Path) -> None:
    Path(path).write_text(to_json(candidate), encoding="utf-8")


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------

def to_markdown(candidate: CandidateDeck) -> str:
    lines: list[str] = []
    lines.append(f"# Deck Candidate #{candidate.rank}: {candidate.deck.name}\n")
    lines.append(f"**Score:** {candidate.score.total:.1f}/100  ")
    lines.append(f"**Archetype:** {candidate.report.archetype.primary_archetype}  ")
    lines.append(f"**Legal:** {'Yes' if candidate.score.is_legal else 'No'}  ")
    lines.append(f"**Strategy used:** {candidate.generation_strategy}\n")

    if candidate.seed_cards:
        lines.append(f"**Built around:** {', '.join(candidate.seed_cards)}\n")

    lines.append("## Objective Scores\n")
    for obj_name, score in candidate.score.objective_breakdown.items():
        lines.append(f"- **{obj_name}:** {score:.1f}")
    lines.append("")

    lines.append("## PTCG Live Export\n```")
    lines.append(to_ptcg_live(candidate))
    lines.append("```\n")

    lines.append("## Why These Cards\n")
    for card_name, reason in candidate.card_selection_reasons.items():
        lines.append(f"- **{card_name}:** {reason}")
    lines.append("")

    if candidate.suggested_upgrades:
        lines.append("## Suggested Upgrades\n")
        for upgrade in candidate.suggested_upgrades:
            lines.append(f"- {upgrade}")
        lines.append("")

    # Delegate to Phase 5's Markdown report for detailed analysis
    lines.append("## Full Analysis\n")
    lines.append(deck_markdown(candidate.report))

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CSV (build result summary)
# ---------------------------------------------------------------------------

def to_csv_build_result(result: BuildResult) -> str:
    buf = io.StringIO()
    fieldnames = [
        "rank", "deck_name", "score", "is_legal", "archetype", "strategy",
        "consistency_score", "synergy_score", "draw_power", "search_power",
        "pokemon_count", "trainer_count", "energy_count", "max_damage",
    ]
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    for c in result.ranked():
        writer.writerow({
            "rank": c.rank,
            "deck_name": c.deck.name,
            "score": c.score.total,
            "is_legal": c.score.is_legal,
            "archetype": c.report.archetype.primary_archetype,
            "strategy": c.generation_strategy,
            "consistency_score": c.report.consistency.consistency_score,
            "synergy_score": c.report.synergy.synergy_score,
            "draw_power": c.report.metrics.draw_power,
            "search_power": c.report.metrics.search_power,
            "pokemon_count": c.report.metrics.pokemon_count,
            "trainer_count": c.report.metrics.trainer_count,
            "energy_count": c.report.metrics.energy_count,
            "max_damage": c.report.metrics.max_damage,
        })
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Terminal
# ---------------------------------------------------------------------------

def to_terminal(candidate: CandidateDeck) -> str:
    sep = "=" * 60
    lines = [
        sep,
        f"  CANDIDATE #{candidate.rank}: {candidate.deck.name}",
        f"  Score: {candidate.score.total:.1f}/100  Legal: {candidate.score.is_legal}",
        f"  Archetype: {candidate.report.archetype.primary_archetype}  Strategy: {candidate.generation_strategy}",
        sep,
    ]
    if candidate.seed_cards:
        lines.append(f"  Built around: {', '.join(candidate.seed_cards[:3])}")
    lines.append("")
    lines.append(deck_terminal(candidate.report))
    lines.append("")
    if candidate.suggested_upgrades:
        lines.append("  SUGGESTED UPGRADES:")
        for u in candidate.suggested_upgrades[:5]:
            lines.append(f"    → {u}")
    lines.append(sep)
    return "\n".join(lines)


def to_terminal_build_result(result: BuildResult) -> str:
    lines = [f"\n{'=' * 60}",
             f"  BUILD RESULT: {result.request_summary}",
             f"  {len(result.candidates)} candidates generated",
             "=" * 60]
    for c in result.ranked():
        lines.append(
            f"  #{c.rank:2d}  {c.score.total:5.1f}/100  "
            f"{c.report.archetype.primary_archetype:<18} "
            f"{'LEGAL' if c.score.is_legal else 'ILLEGAL':8} "
            f"{c.generation_strategy}"
        )
    return "\n".join(lines)
