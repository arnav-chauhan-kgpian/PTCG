"""
Edge factory helpers.

All edge creation goes through these functions so that:
  1. Bidirectional links are generated consistently.
  2. Weights are normalised.
  3. Duplicate-detection keys are stable.
"""

from __future__ import annotations

from src.cards.relationships.models import (
    INVERSE,
    CardEdge,
    RelationshipType,
)

# ---------------------------------------------------------------------------
# Default weights per relationship type
# ---------------------------------------------------------------------------

BASE_WEIGHT: dict[RelationshipType, float] = {
    RelationshipType.EVOLVES_FROM:        1.0,
    RelationshipType.EVOLVES_TO:          1.0,
    RelationshipType.SEARCHES_FOR:        0.85,
    RelationshipType.SEARCHED_BY:         0.85,
    RelationshipType.ACCELERATES_ENERGY:  0.80,
    RelationshipType.USES_ENERGY:         0.80,
    RelationshipType.ENERGY_SYNERGY:      0.65,
    RelationshipType.HEALS:               0.70,
    RelationshipType.PROTECTS:            0.70,
    RelationshipType.DAMAGE_REDUCTION:    0.60,
    RelationshipType.SWITCHES:            0.55,
    RelationshipType.BENCH_SUPPORT:       0.55,
    RelationshipType.DRAW_ENGINE:         0.75,
    RelationshipType.CONSISTENCY:         0.60,
    RelationshipType.DISCARD_ENGINE:      0.50,
    RelationshipType.RECOVERY:            0.55,
    RelationshipType.ABILITY_SUPPORT:     0.60,
    RelationshipType.ABILITY_COUNTER:     0.65,
    RelationshipType.STADIUM_SUPPORT:     0.50,
    RelationshipType.TOOL_SUPPORT:        0.50,
    RelationshipType.ITEM_SUPPORT:        0.50,
    RelationshipType.SUPPORTER_SUPPORT:   0.50,
    RelationshipType.DAMAGE_BOOST:        0.70,
    RelationshipType.TYPE_SYNERGY:        0.40,
    RelationshipType.STATUS_SYNERGY:      0.45,
    RelationshipType.SPECIAL_CONDITION:   0.45,
    RelationshipType.COUNTERS:            0.65,
    RelationshipType.ANTI_META:           0.55,
    RelationshipType.LOCK:                0.60,
    RelationshipType.SELF_SETUP:          0.50,
    RelationshipType.FINISHER:            0.60,
    RelationshipType.UNKNOWN:             0.10,
}


def default_weight(rel: RelationshipType) -> float:
    return BASE_WEIGHT.get(rel, 0.5)


# ---------------------------------------------------------------------------
# Edge creation
# ---------------------------------------------------------------------------


def make_edge(
    source: str,
    target: str,
    rel: RelationshipType,
    *,
    reason: str = "",
    confidence: float = 1.0,
    evidence: tuple[str, ...] = (),
    weight: float | None = None,
) -> CardEdge:
    """Create a single directional CardEdge."""
    w = weight if weight is not None else default_weight(rel)
    w = min(1.0, max(0.0, w * confidence))
    return CardEdge(
        source=source,
        target=target,
        relationship_type=rel,
        weight=w,
        reason=reason,
        confidence=confidence,
        evidence=evidence,
    )


def make_pair(
    source: str,
    target: str,
    rel: RelationshipType,
    *,
    reason: str = "",
    confidence: float = 1.0,
    evidence: tuple[str, ...] = (),
    weight: float | None = None,
) -> list[CardEdge]:
    """Create a forward edge and its automatic inverse (if one exists)."""
    forward = make_edge(source, target, rel, reason=reason, confidence=confidence,
                        evidence=evidence, weight=weight)
    edges = [forward]

    inv = INVERSE.get(rel)
    if inv is not None and inv != rel:
        reverse = make_edge(target, source, inv, reason=f"inverse of: {reason}",
                            confidence=confidence, evidence=evidence, weight=weight)
        edges.append(reverse)
    return edges


def merge_edges(edges: list[CardEdge]) -> list[CardEdge]:
    """Merge duplicate edges (same source/target/type) by combining evidence and averaging weight."""
    buckets: dict[tuple[str, str, str], list[CardEdge]] = {}
    for e in edges:
        key = e.edge_key
        buckets.setdefault(key, []).append(e)

    merged: list[CardEdge] = []
    for key, group in buckets.items():
        if len(group) == 1:
            merged.append(group[0])
            continue
        all_evidence = tuple({ev for e in group for ev in e.evidence})
        avg_confidence = sum(e.confidence for e in group) / len(group)
        # Weight increases with multiple evidence sources (capped at 1.0)
        base_w = max(e.weight for e in group)
        boosted_w = min(1.0, base_w + 0.05 * (len(group) - 1))
        combined_reasons = "; ".join({e.reason for e in group if e.reason})
        merged.append(CardEdge(
            source=group[0].source,
            target=group[0].target,
            relationship_type=group[0].relationship_type,
            weight=boosted_w,
            reason=combined_reasons,
            confidence=avg_confidence,
            evidence=all_evidence,
        ))
    return merged
