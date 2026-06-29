"""
Edge scoring utilities.

Scores can be recomputed or used for ranking after graph construction.
"""

from __future__ import annotations

from src.cards.relationships.models import CardEdge, RelationshipType

# Specificity bonus: more specific relationships rank higher
_SPECIFICITY: dict[RelationshipType, float] = {
    RelationshipType.EVOLVES_FROM:       1.0,
    RelationshipType.EVOLVES_TO:         1.0,
    RelationshipType.SEARCHES_FOR:       0.9,
    RelationshipType.SEARCHED_BY:        0.9,
    RelationshipType.ACCELERATES_ENERGY: 0.85,
    RelationshipType.DRAW_ENGINE:        0.80,
    RelationshipType.HEALS:              0.75,
    RelationshipType.PROTECTS:           0.75,
    RelationshipType.DAMAGE_BOOST:       0.70,
    RelationshipType.FINISHER:           0.70,
    RelationshipType.ABILITY_COUNTER:    0.65,
    RelationshipType.COUNTERS:           0.65,
    RelationshipType.ENERGY_SYNERGY:     0.60,
    RelationshipType.USES_ENERGY:        0.55,
    RelationshipType.CONSISTENCY:        0.55,
    RelationshipType.SWITCHES:           0.55,
    RelationshipType.BENCH_SUPPORT:      0.50,
    RelationshipType.RECOVERY:           0.50,
    RelationshipType.TYPE_SYNERGY:       0.30,
    RelationshipType.UNKNOWN:            0.05,
}


def specificity(rel: RelationshipType) -> float:
    return _SPECIFICITY.get(rel, 0.4)


def score_edge(edge: CardEdge) -> float:
    """Compute a composite score for an edge.

    Factors:
      - base weight (already incorporates default_weight × confidence)
      - specificity of the relationship type
      - evidence quantity (more evidence = more certain)
    """
    evidence_bonus = min(0.15, len(edge.evidence) * 0.03)
    spec = specificity(edge.relationship_type)
    return min(1.0, edge.weight * 0.6 + spec * 0.3 + evidence_bonus + edge.confidence * 0.1)


def rank_edges(edges: list[CardEdge]) -> list[CardEdge]:
    """Return edges sorted by composite score descending."""
    return sorted(edges, key=score_edge, reverse=True)


def top_k_neighbors(
    edges: list[CardEdge],
    k: int = 10,
) -> list[tuple[str, float]]:
    """From a list of outgoing edges, return (target, score) top-k pairs."""
    seen: dict[str, float] = {}
    for e in edges:
        s = score_edge(e)
        if e.target not in seen or s > seen[e.target]:
            seen[e.target] = s
    return sorted(seen.items(), key=lambda x: -x[1])[:k]
