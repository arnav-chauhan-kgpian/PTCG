"""
DeckAnalyzer — main orchestrator for the Deck Intelligence Engine.

Accepts decks in multiple formats, validates, and runs all analysis modules.
"""

from __future__ import annotations

import csv
import io
import json
import re
from typing import Any

from loguru import logger

from src.cards.relationships.graph import CardGraph
from src.cards.types import AnyCard
from src.decks.archetypes import detect_archetype
from src.decks.consistency import compute_consistency
from src.decks.curves import compute_curves
from src.decks.matchup import compute_matchups
from src.decks.metrics import compute_metrics
from src.decks.models import Deck, DeckSlot
from src.decks.reports import DeckReport, assemble_report
from src.decks.synergy import compute_synergy
from src.decks.validators import DeckValidator
from src.decks.win_conditions import compute_win_conditions

# ---------------------------------------------------------------------------
# Input parsing
# ---------------------------------------------------------------------------


def parse_deck(
    source: Any,
    card_db: dict[str, AnyCard] | None = None,
    *,
    name: str = "Unnamed Deck",
) -> Deck:
    """Parse a deck from any supported input format.

    Supported formats:
    - list[DeckSlot]
    - list[AnyCard]          → each card = 1 copy
    - list[tuple[AnyCard, int]]
    - dict[str, int]         → {card_name_or_id: count}
    - JSON string            → dict or list
    - CSV string             → "name,count" or "id,count" rows
    - Text deck list         → "4 Charizard ex PAR 242\\n3 Pidgey..."
    """
    if isinstance(source, Deck):
        return source

    if isinstance(source, (list, tuple)):
        return _parse_list(source, name=name)

    if isinstance(source, dict):
        if card_db is None:
            raise ValueError("card_db required for dict input format")
        return _parse_dict(source, card_db, name=name)

    if isinstance(source, str):
        return _parse_string(source, card_db, name=name)

    raise TypeError(f"Unsupported deck input type: {type(source)}")


def _parse_list(source: list | tuple, *, name: str) -> Deck:
    slots: list[DeckSlot] = []

    for item in source:
        if isinstance(item, DeckSlot):
            slots.append(item)
        elif isinstance(item, (list, tuple)) and len(item) == 2:
            card, count = item
            slots.append(DeckSlot(card=card, count=int(count)))
        else:
            # Assume it's a card with count=1
            slots.append(DeckSlot(card=item, count=1))

    return Deck(name=name, slots=tuple(slots))


def _parse_dict(source: dict, card_db: dict[str, AnyCard], *, name: str) -> Deck:
    """dict keys may be card names or string IDs."""
    slots: list[DeckSlot] = []
    for key, count in source.items():
        card = card_db.get(key) or card_db.get(str(key))
        if card is None:
            raise KeyError(f"Card not found in database: {key!r}")
        slots.append(DeckSlot(card=card, count=int(count)))
    return Deck(name=name, slots=tuple(slots))


def _parse_string(source: str, card_db: dict[str, AnyCard] | None, *, name: str) -> Deck:
    source = source.strip()

    # Try JSON first
    if source.startswith(("{", "[")):
        data = json.loads(source)
        if isinstance(data, dict):
            if card_db is None:
                raise ValueError("card_db required for JSON dict format")
            return _parse_dict(data, card_db, name=name)
        if isinstance(data, list):
            return _parse_list(data, name=name)

    # Try CSV
    if "," in source.splitlines()[0] if source.splitlines() else "":
        reader = csv.DictReader(io.StringIO(source))
        if reader.fieldnames and any(f in reader.fieldnames for f in ("name", "id", "card_name")):
            if card_db is None:
                raise ValueError("card_db required for CSV format")
            slots: list[DeckSlot] = []
            for row in reader:
                key = row.get("name") or row.get("card_name") or row.get("id", "")
                count = int(row.get("count", row.get("qty", 1)))
                card = card_db.get(key)
                if card is None:
                    raise KeyError(f"Card not found: {key!r}")
                slots.append(DeckSlot(card=card, count=count))
            return Deck(name=name, slots=tuple(slots))

    # Text deck list: "4 Charizard ex PAR 242" or "4x Charizard ex"
    return _parse_text_list(source, card_db, name=name)


_DECKLIST_LINE = re.compile(
    r"^(\d+)x?\s+(.+?)(?:\s+[A-Z]{2,4}\s+\d+)?$",
    re.IGNORECASE,
)


def _parse_text_list(source: str, card_db: dict[str, AnyCard] | None, *, name: str) -> Deck:
    """Parse PTCG-standard text deck lists."""
    if card_db is None:
        raise ValueError("card_db required for text deck list format")

    slots: list[DeckSlot] = []
    for line in source.splitlines():
        line = line.strip()
        if not line or line.startswith("//") or line.startswith("#"):
            continue
        # Section headers like "Pokémon: 18", "Trainers:", "Energy:"
        if re.match(r"^(pokemon|trainer|energy|item|supporter)", line, re.IGNORECASE) and ":" in line:
            continue

        m = _DECKLIST_LINE.match(line)
        if not m:
            logger.debug("Deck list: skipping unmatched line: {!r}", line)
            continue

        count = int(m.group(1))
        card_name = m.group(2).strip()

        # Try exact name match, then case-insensitive
        card = card_db.get(card_name)
        if card is None:
            lower = card_name.lower()
            card = next((c for n, c in card_db.items() if n.lower() == lower), None)
        if card is None:
            logger.warning("Deck list: card not found: {!r}", card_name)
            continue

        slots.append(DeckSlot(card=card, count=count))

    return Deck(name=name, slots=tuple(slots))


# ---------------------------------------------------------------------------
# Analyzer
# ---------------------------------------------------------------------------


class DeckAnalyzer:
    """
    Complete deck analysis engine.

    Usage::

        analyzer = DeckAnalyzer(graph)
        report = analyzer.analyze(deck)
        print(exports.to_terminal(report))
    """

    def __init__(self, graph: CardGraph) -> None:
        self._graph = graph
        self._validator = DeckValidator()

    def analyze(self, deck: Deck | Any, **parse_kwargs) -> DeckReport:
        """Analyze a deck.  Accepts any format supported by parse_deck()."""
        if not isinstance(deck, Deck):
            deck = parse_deck(deck, **parse_kwargs)

        logger.debug("DeckAnalyzer: analyzing '{}' ({} total cards)", deck.name, deck.total_count)

        validation = self._validator.validate(deck)
        metrics = compute_metrics(deck)
        curves = compute_curves(deck)
        consistency = compute_consistency(deck, metrics)
        synergy = compute_synergy(deck, self._graph)
        archetype = detect_archetype(metrics, curves)
        win_conds = compute_win_conditions(deck, metrics, self._graph)
        matchup = compute_matchups(metrics, curves, archetype)

        graph_stats = {
            "deck_cards_in_graph": sum(
                1 for s in deck.slots
                if self._graph.node(s.card_id) is not None
            ),
            "total_graph_nodes": self._graph.node_count,
            "total_graph_edges": self._graph.edge_count,
            "internal_deck_edges": synergy.internal_edge_count,
        }

        report = assemble_report(
            deck_name=deck.name or "Unnamed Deck",
            validation=validation,
            metrics=metrics,
            curves=curves,
            consistency=consistency,
            synergy=synergy,
            archetype=archetype,
            win_conditions=win_conds,
            matchup=matchup,
            graph_stats=graph_stats,
        )

        logger.info(
            "DeckAnalyzer: {} — {} archetype, consistency={}, synergy={:.0f}/100",
            deck.name,
            archetype.primary_archetype,
            consistency.consistency_grade,
            synergy.synergy_score,
        )

        return report

    def analyze_raw(
        self,
        source: Any,
        card_db: dict[str, AnyCard],
        *,
        name: str = "Unnamed Deck",
    ) -> DeckReport:
        """Parse source using card_db lookup, then analyze."""
        deck = parse_deck(source, card_db=card_db, name=name)
        return self.analyze(deck)
