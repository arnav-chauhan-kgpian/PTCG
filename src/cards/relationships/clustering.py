"""
Community detection — discovers archetypes automatically.

Uses NetworkX community algorithms on an undirected weighted projection
of the card graph.

Algorithm preference order (falls back gracefully):
  1. Louvain (best modularity, available in NetworkX ≥ 3.0)
  2. Greedy modularity (always available)
  3. Label propagation (fallback)
  4. Connected components (absolute fallback)
"""

from __future__ import annotations

from collections import Counter, defaultdict

import networkx as nx
from loguru import logger

from src.cards.enums import PokemonType
from src.cards.relationships.graph import CardGraph
from src.cards.relationships.models import CardNode, Community


def _detect_communities(
    ug: nx.Graph,
) -> list[frozenset[str]]:
    """Run community detection with automatic algorithm fallback."""
    if ug.number_of_nodes() < 2:
        return [frozenset(ug.nodes)]

    # Try Louvain (NetworkX ≥ 3.0)
    try:
        communities = list(nx.community.louvain_communities(ug, seed=42, weight="weight"))
        logger.debug("Community detection: Louvain → {} communities", len(communities))
        return [frozenset(c) for c in communities]
    except AttributeError:
        pass
    except Exception as exc:
        logger.warning("Louvain failed: {}; falling back", exc)

    # Try greedy modularity
    try:
        communities = list(nx.community.greedy_modularity_communities(ug, weight="weight"))
        logger.debug("Community detection: greedy_modularity → {} communities", len(communities))
        return [frozenset(c) for c in communities]
    except Exception as exc:
        logger.warning("Greedy modularity failed: {}; falling back", exc)

    # Label propagation
    try:
        communities = list(nx.community.label_propagation_communities(ug))
        logger.debug("Community detection: label_propagation → {} communities", len(communities))
        return [frozenset(c) for c in communities]
    except Exception as exc:
        logger.warning("Label propagation failed: {}; falling back to connected components", exc)

    # Connected components — last resort
    components = list(nx.connected_components(ug))
    logger.debug("Community detection: connected_components → {} communities", len(components))
    return [frozenset(c) for c in components]


def _dominant_pokemon_type(
    nodes: list[CardNode],
) -> PokemonType | None:
    types = [n.pokemon_type for n in nodes if n.pokemon_type is not None]
    if not types:
        return None
    most_common = Counter(types).most_common(1)
    return most_common[0][0] if most_common else None


def _dominant_energy(
    nodes: list[CardNode],
) -> PokemonType | None:
    provides: list[PokemonType] = []
    for n in nodes:
        provides.extend(n.provides)
    if not provides:
        return None
    return Counter(provides).most_common(1)[0][0]


def _key_trainers(
    nodes: list[CardNode],
    graph: CardGraph,
    *,
    top_n: int = 5,
) -> tuple[str, ...]:
    """Find trainer card IDs with the most connections inside the community."""
    from src.cards.enums import CardSuperType
    trainer_ids = [n.card_id for n in nodes if n.card_super_type == CardSuperType.TRAINER]
    # Sort by in-degree within the community
    community_ids = {n.card_id for n in nodes}
    scores: dict[str, int] = {}
    for tid in trainer_ids:
        scores[tid] = sum(
            1 for e in graph.edges_from(tid) if e.target in community_ids
        )
    return tuple(sorted(scores, key=lambda x: -scores[x])[:top_n])


def _shared_mechanics(
    member_ids: frozenset[str],
    graph: CardGraph,
) -> tuple[str, ...]:
    """Most common relationship types within this community."""
    counts: dict[str, int] = defaultdict(int)
    for eid in member_ids:
        for e in graph.edges_from(eid):
            if e.target in member_ids:
                counts[e.relationship_type.value] += 1
    return tuple(k for k, _ in sorted(counts.items(), key=lambda x: -x[1])[:5])


def detect_communities(graph: CardGraph) -> list[Community]:
    """Run community detection and return Community objects."""
    ug = graph.to_undirected()

    if ug.number_of_nodes() == 0:
        return []

    raw_communities = _detect_communities(ug)

    # Sort by size descending
    raw_communities.sort(key=len, reverse=True)

    communities: list[Community] = []
    for idx, member_ids in enumerate(raw_communities):
        nodes = [graph.node(cid) for cid in member_ids if graph.node(cid) is not None]
        nodes = [n for n in nodes if n is not None]  # type: ignore[misc]

        size = len(nodes)
        if size == 0:
            continue

        # Classify core vs support by degree
        degree_map: dict[str, int] = {}
        for n in nodes:
            degree_map[n.card_id] = sum(
                1 for e in graph.edges_from(n.card_id)
                if e.target in member_ids and e.target != n.card_id
            )
        sorted_by_degree = sorted(degree_map, key=lambda x: -degree_map[x])

        split = max(1, size // 3)
        core_cards = tuple(sorted_by_degree[:split])
        support_cards = tuple(sorted_by_degree[split:])

        # Count internal edges
        internal = sum(
            1 for n in nodes
            for e in graph.edges_from(n.card_id)
            if e.target in member_ids and e.target != n.card_id
        )

        # Density = actual internal edges / possible internal edges
        possible = size * (size - 1)
        density = internal / possible if possible > 0 else 0.0

        communities.append(Community(
            community_id=idx,
            core_cards=core_cards,
            support_cards=support_cards,
            shared_mechanics=_shared_mechanics(member_ids, graph),
            dominant_energy=_dominant_energy(nodes),
            dominant_pokemon_type=_dominant_pokemon_type(nodes),
            key_trainers=_key_trainers(nodes, graph),
            size=size,
            internal_edge_count=internal,
            density=density,
        ))

    logger.info("Detected {} communities (sizes: {})",
                len(communities),
                [c.size for c in communities[:10]])
    return communities
