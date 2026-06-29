"""
Synergy analysis using the relationship graph.

Measures how well the deck cards connect to each other and
identifies missing support, orphans, and combo density.
"""

from __future__ import annotations

from collections import defaultdict

from pydantic import BaseModel, ConfigDict

from src.cards.relationships.graph import CardGraph
from src.decks.models import Deck


class SynergyReport(BaseModel):
    """Synergy analysis for a deck against the full card graph."""

    model_config = ConfigDict(frozen=True)

    # Internal synergy: edges between deck cards only
    internal_edge_count: int
    internal_edge_density: float       # edges / possible pairs

    # Orphan cards: cards with 0 edges to any other deck card
    orphan_cards: tuple[str, ...]      # card names

    # Highly connected cards (combo anchors)
    combo_anchors: tuple[str, ...]     # top-5 by internal degree

    # Missing support: top recommended cards NOT in deck
    missing_support: tuple[str, ...]   # card names (up to 10)

    # Redundant cards: multiple cards filling the same role
    redundant_roles: tuple[str, ...]   # role descriptions

    # Required cards: cards that are depended on by many others in deck
    critical_cards: tuple[str, ...]    # card names

    # Engine cohesion: 0–100 score
    engine_cohesion: float

    # Synergy score: overall 0–100
    synergy_score: float

    # Relationship type breakdown within deck
    internal_relationship_breakdown: dict[str, int]


def compute_synergy(deck: Deck, graph: CardGraph) -> SynergyReport:
    deck_ids = deck.unique_card_ids()
    id_to_name: dict[str, str] = {s.card_id: s.name for s in deck.slots}

    # Internal edges: source AND target both in deck
    internal_edges: list = []
    rel_breakdown: dict[str, int] = defaultdict(int)
    degree: dict[str, int] = defaultdict(int)  # card_id → internal degree

    for card_id in deck_ids:
        for edge in graph.edges_from(card_id):
            if edge.target in deck_ids and edge.target != card_id:
                internal_edges.append(edge)
                rel_breakdown[edge.relationship_type.value] += 1
                degree[card_id] += 1

    n_cards = len(deck_ids)
    max_possible = n_cards * (n_cards - 1)  # directed pairs
    edge_density = len(internal_edges) / max_possible if max_possible > 0 else 0.0

    # Orphan cards: no internal edges at all
    orphans = [id_to_name.get(cid, cid) for cid in deck_ids if degree[cid] == 0]

    # Combo anchors: top 5 by internal degree
    sorted_by_degree = sorted(deck_ids, key=lambda c: -degree[c])
    anchors = [id_to_name.get(c, c) for c in sorted_by_degree[:5]]

    # Missing support: for each deck card, look at its recommended partners
    # that are NOT in the deck — aggregate top mentions
    support_mentions: dict[str, int] = defaultdict(int)
    for card_id in deck_ids:
        profile = graph.profile(card_id)
        if profile is None:
            continue
        for rec in profile.recommended_with[:10]:
            if rec not in deck_ids:
                name = graph.node(rec)
                if name:
                    support_mentions[name.name] += 1

    missing_support = [
        name for name, _ in sorted(support_mentions.items(), key=lambda x: -x[1])[:10]
    ]

    # Critical cards: in deck AND required_by many others in deck
    critical_mentions: dict[str, int] = defaultdict(int)
    for card_id in deck_ids:
        profile = graph.profile(card_id)
        if profile is None:
            continue
        for req in profile.requires:
            if req in deck_ids:
                critical_mentions[req] += 1

    critical = [
        id_to_name.get(cid, cid)
        for cid, _ in sorted(critical_mentions.items(), key=lambda x: -x[1])[:5]
    ]

    # Redundant roles: multiple cards with same primary_role
    role_cards: dict[str, list[str]] = defaultdict(list)
    for card_id in deck_ids:
        profile = graph.profile(card_id)
        if profile and profile.primary_role:
            role_cards[profile.primary_role.value].append(id_to_name.get(card_id, card_id))

    redundant_roles = [
        f"{role}: {', '.join(cards)}"
        for role, cards in role_cards.items()
        if len(cards) >= 3
    ]

    # Engine cohesion: ratio of non-orphan cards
    non_orphan_ratio = 1.0 - len(orphans) / n_cards if n_cards > 0 else 0.0
    edge_score = min(1.0, edge_density * 10)
    engine_cohesion = round((non_orphan_ratio * 0.6 + edge_score * 0.4) * 100, 1)

    # Synergy score: cohesion + density bonus
    synergy_score = round(
        engine_cohesion * 0.7
        + min(30.0, len(internal_edges) / 5)
        + max(0.0, 10.0 - len(orphans) * 2),
        1,
    )
    synergy_score = min(100.0, synergy_score)

    return SynergyReport(
        internal_edge_count=len(internal_edges),
        internal_edge_density=round(edge_density, 4),
        orphan_cards=tuple(orphans),
        combo_anchors=tuple(anchors),
        missing_support=tuple(missing_support),
        redundant_roles=tuple(redundant_roles),
        critical_cards=tuple(critical),
        engine_cohesion=engine_cohesion,
        synergy_score=synergy_score,
        internal_relationship_breakdown=dict(rel_breakdown),
    )
