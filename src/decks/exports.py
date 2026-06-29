"""
Export DeckReport to JSON, Markdown, CSV, and terminal output.
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

from src.decks.reports import DeckReport


def to_dict(report: DeckReport) -> dict:
    """Full report as a nested dict (JSON-serialisable)."""
    return report.model_dump(mode="json")


def to_json(report: DeckReport, *, indent: int = 2) -> str:
    """Full report as a JSON string."""
    return json.dumps(to_dict(report), indent=indent, ensure_ascii=False)


def write_json(report: DeckReport, path: str | Path) -> None:
    Path(path).write_text(to_json(report), encoding="utf-8")


def to_markdown(report: DeckReport) -> str:
    """Human-readable Markdown report."""
    m = report.metrics
    c = report.consistency
    cr = report.curves
    s = report.synergy
    a = report.archetype
    w = report.win_conditions
    lines: list[str] = []

    def h(level: int, text: str) -> None:
        lines.append(f"{'#' * level} {text}\n")

    def bullet(text: str) -> None:
        lines.append(f"- {text}")

    def kv(key: str, val) -> None:
        lines.append(f"- **{key}:** {val}")

    h(1, f"Deck Report: {report.deck_name}")

    lines.append(f"> **Legal:** {'✅ Yes' if report.is_legal else '❌ No'}  ")
    lines.append(f"> **Archetype:** {a.primary_archetype}  ")
    lines.append(f"> **Speed:** {cr.speed_rating}  ")
    lines.append(f"> **Consistency:** {c.consistency_grade} ({c.consistency_score:.0f}/100)  \n")

    h(2, "Summary")
    lines.append(report.overall_summary + "\n")

    h(2, "Strengths")
    for s_ in report.strengths:
        bullet(s_)
    lines.append("")

    h(2, "Weaknesses")
    for w_ in report.weaknesses:
        bullet(w_)
    lines.append("")

    h(2, "Risk Factors")
    for r in report.risk_factors:
        bullet(r)
    lines.append("")

    h(2, "Deck Composition")
    kv("Total cards", m.total_cards)
    kv("Pokémon", f"{m.pokemon_count} ({m.basic_pokemon_count} Basic, {m.stage1_count} Stage 1, {m.stage2_count} Stage 2)")
    kv("Trainers", f"{m.trainer_count} ({m.supporter_count} Supporters, {m.item_count} Items, {m.stadium_count} Stadiums, {m.tool_count} Tools)")
    kv("Energy", f"{m.energy_count} ({m.basic_energy_count} Basic, {m.special_energy_count} Special)")
    kv("Rule-box Pokémon", m.rule_box_count)
    kv("ACE SPEC cards", m.ace_spec_count)
    lines.append("")

    h(2, "Stats")
    kv("Avg HP", f"{m.avg_hp} (max {m.max_hp}, min {m.min_hp})")
    kv("Avg damage", f"{m.avg_damage} (max {m.max_damage})")
    kv("Avg attack cost", m.avg_attack_cost)
    kv("Avg retreat", m.avg_retreat)
    kv("Prize liability", f"{m.prize_liability_score:.1%}")
    lines.append("")

    h(2, "Consistency")
    for note in report.consistency_notes:
        bullet(note)
    lines.append("")

    h(2, "Energy Notes")
    for note in report.energy_notes:
        bullet(note)
    lines.append("")

    h(2, "Synergy")
    kv("Engine cohesion", f"{s.engine_cohesion:.0f}/100")
    kv("Internal edges", s.internal_edge_count)
    kv("Synergy score", f"{s.synergy_score:.0f}/100")
    if s.combo_anchors:
        kv("Combo anchors", ", ".join(s.combo_anchors))
    if s.orphan_cards:
        kv("Orphan cards", ", ".join(s.orphan_cards))
    if s.missing_support:
        kv("Missing support", ", ".join(s.missing_support))
    lines.append("")

    h(2, "Win Conditions")
    kv("Primary", w.primary_win_condition)
    if w.secondary_win_condition:
        kv("Secondary", w.secondary_win_condition)
    kv("Fallback", w.fallback_strategy)
    kv("Finishers", ", ".join(w.finishers) if w.finishers else "None identified")
    kv("Core engine", ", ".join(w.core_engine) if w.core_engine else "N/A")
    if w.dependency_chains:
        kv("Evolution chains", "; ".join(w.dependency_chains))
    kv("Expected prize turns", w.expected_prize_turns)
    lines.append("")

    h(2, "Archetype Detection")
    lines.append(a.explanation + "\n")
    h(3, "All Hypotheses")
    for hyp in a.hypotheses[:5]:
        bullet(f"{hyp.archetype}: {hyp.confidence:.0%} — {', '.join(hyp.evidence) or 'no strong signals'}")
    lines.append("")

    h(2, "Matchup Tendencies")
    for mu in report.matchup.matchups:
        bullet(f"**vs {mu.opponent_strategy}:** {mu.rating} — {mu.explanation}")
    lines.append("")

    if report.missing_cards:
        h(2, "Missing Cards")
        for card in report.missing_cards:
            bullet(card)
        lines.append("")

    if report.replacement_suggestions:
        h(2, "Replacement Suggestions")
        for current, suggested in report.replacement_suggestions:
            bullet(f"{current} → {suggested}")
        lines.append("")

    if not report.is_legal:
        h(2, "Validation Errors")
        for issue in report.validation.errors:
            bullet(f"[{issue.code}] {issue.message}")
        lines.append("")

    return "\n".join(lines)


def to_csv_summary(report: DeckReport) -> str:
    """Single-row CSV with key metrics (suitable for spreadsheet import)."""
    m = report.metrics
    c = report.consistency
    cr = report.curves
    s = report.synergy
    a = report.archetype

    fields = {
        "deck_name": report.deck_name,
        "is_legal": report.is_legal,
        "archetype": a.primary_archetype,
        "prize_model": a.prize_model,
        "speed_rating": cr.speed_rating,
        "consistency_score": c.consistency_score,
        "consistency_grade": c.consistency_grade,
        "synergy_score": s.synergy_score,
        "engine_cohesion": s.engine_cohesion,
        "pokemon_count": m.pokemon_count,
        "trainer_count": m.trainer_count,
        "energy_count": m.energy_count,
        "basic_pokemon_count": m.basic_pokemon_count,
        "stage1_count": m.stage1_count,
        "stage2_count": m.stage2_count,
        "supporter_count": m.supporter_count,
        "draw_power": m.draw_power,
        "search_power": m.search_power,
        "avg_hp": m.avg_hp,
        "max_hp": m.max_hp,
        "avg_damage": m.avg_damage,
        "max_damage": m.max_damage,
        "avg_attack_cost": m.avg_attack_cost,
        "avg_retreat": m.avg_retreat,
        "energy_acceleration": m.energy_acceleration,
        "disruption_score": m.disruption_score,
        "prize_liability_score": m.prize_liability_score,
        "rule_box_count": m.rule_box_count,
        "p_opening_basic": c.p_opening_basic,
        "expected_mulligans": c.expected_mulligans,
        "internal_edges": s.internal_edge_count,
        "orphan_count": len(s.orphan_cards),
        "best_matchup": report.matchup.best_matchup,
        "worst_matchup": report.matchup.worst_matchup,
        "overall_matchup_score": report.matchup.overall_matchup_score,
    }

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(fields.keys()))
    writer.writeheader()
    writer.writerow(fields)
    return buf.getvalue()


def write_csv(report: DeckReport, path: str | Path) -> None:
    Path(path).write_text(to_csv_summary(report), encoding="utf-8")


def to_terminal(report: DeckReport) -> str:
    """Compact coloured terminal output (plain text, no ANSI codes)."""
    lines: list[str] = []
    m = report.metrics
    c = report.consistency
    cr = report.curves
    s = report.synergy
    a = report.archetype
    w = report.win_conditions

    sep = "=" * 60
    lines.append(sep)
    lines.append(f"  DECK REPORT: {report.deck_name.upper()}")
    lines.append(sep)
    lines.append(f"  Legal:      {'YES' if report.is_legal else 'NO — ' + '; '.join(e.message for e in report.validation.errors[:2])}")
    lines.append(f"  Archetype:  {a.primary_archetype}" + (f" / {a.secondary_archetype}" if a.secondary_archetype else ""))
    lines.append(f"  Speed:      {cr.speed_rating}")
    lines.append(f"  Prize model:{a.prize_model}")
    lines.append("")
    lines.append(f"  Pokémon:    {m.pokemon_count:2d}  ({m.basic_pokemon_count}B/{m.stage1_count}S1/{m.stage2_count}S2)")
    lines.append(f"  Trainers:   {m.trainer_count:2d}  ({m.supporter_count} Supporters)")
    lines.append(f"  Energy:     {m.energy_count:2d}  ({m.basic_energy_count}B / {m.special_energy_count}Sp)")
    lines.append("")
    lines.append(f"  Consistency:{c.consistency_grade:2s} ({c.consistency_score:.0f}/100)  P(open basic)={c.p_opening_basic:.1%}")
    lines.append(f"  Draw power: {m.draw_power:2d}  Search:{m.search_power:2d}  Recovery:{m.recovery_score:2d}")
    lines.append(f"  Synergy:    {s.synergy_score:.0f}/100  Cohesion:{s.engine_cohesion:.0f}%  Orphans:{len(s.orphan_cards)}")
    lines.append(f"  Avg HP:     {m.avg_hp}  Max dmg:{m.max_damage}  Avg cost:{m.avg_attack_cost}")
    lines.append("")
    lines.append("  STRENGTHS:")
    for st in report.strengths[:3]:
        lines.append(f"    + {st}")
    lines.append("  WEAKNESSES:")
    for wk in report.weaknesses[:3]:
        lines.append(f"    - {wk}")
    lines.append("")
    lines.append(f"  WIN CONDITION: {w.primary_win_condition[:70]}")
    lines.append(f"  FINISHERS:     {', '.join(w.finishers[:3]) or 'none'}")
    lines.append("")
    lines.append("  MATCHUPS:")
    for mu in sorted(report.matchup.matchups, key=lambda x: -x.score)[:4]:
        lines.append(f"    vs {mu.opponent_strategy:<20} {mu.rating}")
    lines.append(sep)
    return "\n".join(lines)
