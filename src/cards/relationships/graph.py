"""
CardGraph — the central in-memory graph of card relationships.

Wraps a NetworkX MultiDiGraph.  Nodes are card IDs (strings).  Edges carry
a CardEdge payload stored under the 'data' attribute.

Thread-safety: the graph is built once and then read-only.  No locking is
needed for concurrent reads (the underlying nx structures are not mutated).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

import networkx as nx
from loguru import logger

from src.cards.relationships.models import (
    DISRUPTION_TYPES,
    SUPPORT_TYPES,
    CardEdge,
    CardNode,
    CardProfile,
    RelationshipType,
)


class CardGraph:
    """Directed multigraph of card relationships.

    Each node stores a CardNode; each edge stores a CardEdge under key 'data'.
    """

    def __init__(self) -> None:
        self._g: nx.MultiDiGraph = nx.MultiDiGraph()
        # Fast lookup indexes (built after all edges are added)
        self._profile_cache: dict[str, CardProfile] = {}
        self._built = False

    # ------------------------------------------------------------------
    # Build-phase API
    # ------------------------------------------------------------------

    def add_node(self, node: CardNode) -> None:
        self._g.add_node(node.card_id, data=node)

    def add_edges(self, edges: Iterable[CardEdge]) -> None:
        for edge in edges:
            self._g.add_edge(
                edge.source,
                edge.target,
                key=edge.relationship_type.value,
                data=edge,
            )

    def finalise(self) -> None:
        """Call once after all nodes/edges are added.  Builds caches."""
        self._profile_cache.clear()
        self._built = True
        logger.info(
            "CardGraph finalised: {} nodes, {} edges",
            self._g.number_of_nodes(),
            self._g.number_of_edges(),
        )

    # ------------------------------------------------------------------
    # Node / edge accessors
    # ------------------------------------------------------------------

    def node(self, card_id: str) -> CardNode | None:
        d = self._g.nodes.get(card_id)
        return d["data"] if d else None

    def all_nodes(self) -> list[CardNode]:
        result = []
        for n in self._g.nodes:
            d = self._g.nodes[n].get("data")
            if d is not None:
                result.append(d)
        return result

    def all_edges(self) -> list[CardEdge]:
        return [
            self._g.edges[u, v, k]["data"]
            for u, v, k in self._g.edges(keys=True)
        ]

    def edges_from(
        self,
        card_id: str,
        rel: RelationshipType | None = None,
    ) -> list[CardEdge]:
        edges = [
            self._g.edges[u, v, k]["data"]
            for u, v, k in self._g.out_edges(card_id, keys=True)
        ]
        if rel is not None:
            edges = [e for e in edges if e.relationship_type == rel]
        return sorted(edges, key=lambda e: -e.weight)

    def edges_to(
        self,
        card_id: str,
        rel: RelationshipType | None = None,
    ) -> list[CardEdge]:
        edges = [
            self._g.edges[u, v, k]["data"]
            for u, v, k in self._g.in_edges(card_id, keys=True)
        ]
        if rel is not None:
            edges = [e for e in edges if e.relationship_type == rel]
        return sorted(edges, key=lambda e: -e.weight)

    def has_edge(
        self,
        source: str,
        target: str,
        rel: RelationshipType | None = None,
    ) -> bool:
        if rel is None:
            return self._g.has_edge(source, target)
        return self._g.has_edge(source, target, key=rel.value)

    def has_node(self, card_id: str) -> bool:
        return card_id in self._g

    # ------------------------------------------------------------------
    # Profile (computed lazily and cached)
    # ------------------------------------------------------------------

    def profile(self, card_id: str) -> CardProfile | None:
        if card_id in self._profile_cache:
            return self._profile_cache[card_id]
        node = self.node(card_id)
        if node is None:
            return None
        p = self._compute_profile(card_id, node)
        self._profile_cache[card_id] = p
        return p

    def _compute_profile(self, card_id: str, node: CardNode) -> CardProfile:
        out_edges = self.edges_from(card_id)
        in_edges = self.edges_to(card_id)

        def targets(edges: list[CardEdge], *rels: RelationshipType) -> tuple[str, ...]:
            rel_set = set(rels)
            seen: set[str] = set()
            result: list[str] = []
            for e in sorted(edges, key=lambda x: -x.weight):
                if e.relationship_type in rel_set and e.target not in seen:
                    seen.add(e.target)
                    result.append(e.target)
            return tuple(result)

        def sources(edges: list[CardEdge], *rels: RelationshipType) -> tuple[str, ...]:
            rel_set = set(rels)
            seen: set[str] = set()
            result: list[str] = []
            for e in sorted(edges, key=lambda x: -x.weight):
                if e.relationship_type in rel_set and e.source not in seen:
                    seen.add(e.source)
                    result.append(e.source)
            return tuple(result)

        supports = targets(out_edges, *SUPPORT_TYPES)
        supported_by = sources(in_edges, *SUPPORT_TYPES)
        counters = targets(out_edges, *DISRUPTION_TYPES)
        countered_by = sources(in_edges, *DISRUPTION_TYPES)

        requires = targets(out_edges, RelationshipType.EVOLVES_FROM, RelationshipType.USES_ENERGY)
        required_by = sources(in_edges, RelationshipType.EVOLVES_TO, RelationshipType.ACCELERATES_ENERGY)

        # Recommended = cards supported-by that aren't just energy/evolution
        synergy_rels = (
            RelationshipType.BENCH_SUPPORT,
            RelationshipType.DRAW_ENGINE,
            RelationshipType.DAMAGE_BOOST,
            RelationshipType.TYPE_SYNERGY,
            RelationshipType.ENERGY_SYNERGY,
            RelationshipType.HEALS,
            RelationshipType.SEARCHES_FOR,
            RelationshipType.ACCELERATES_ENERGY,
        )
        recommended_with = targets(out_edges, *synergy_rels)

        energy_synergies = targets(
            out_edges,
            RelationshipType.ENERGY_SYNERGY,
            RelationshipType.USES_ENERGY,
            RelationshipType.ACCELERATES_ENERGY,
        )
        trainer_synergies = targets(
            out_edges,
            RelationshipType.TOOL_SUPPORT,
            RelationshipType.ITEM_SUPPORT,
            RelationshipType.SUPPORTER_SUPPORT,
            RelationshipType.STADIUM_SUPPORT,
        )
        evolution_family = list(targets(
            out_edges,
            RelationshipType.EVOLVES_FROM,
            RelationshipType.EVOLVES_TO,
        )) + list(sources(
            in_edges,
            RelationshipType.EVOLVES_TO,
            RelationshipType.EVOLVES_FROM,
        ))
        evolution_family_unique: tuple[str, ...] = tuple(dict.fromkeys(evolution_family))

        # Primary role = most common out-edge relationship type
        rel_counts: dict[RelationshipType, int] = defaultdict(int)
        for e in out_edges:
            rel_counts[e.relationship_type] += 1
        sorted_rels = sorted(rel_counts.items(), key=lambda x: -x[1])
        primary_role = sorted_rels[0][0] if sorted_rels else None
        secondary_role = sorted_rels[1][0] if len(sorted_rels) > 1 else None

        return CardProfile(
            card_id=card_id,
            name=node.name,
            supports=supports,
            supported_by=supported_by,
            counters=counters,
            countered_by=countered_by,
            requires=requires,
            required_by=required_by,
            recommended_with=recommended_with,
            conflicts_with=countered_by,
            energy_synergies=energy_synergies,
            trainer_synergies=trainer_synergies,
            evolution_family=evolution_family_unique,
            primary_role=primary_role,
            secondary_role=secondary_role,
            total_in_edges=len(in_edges),
            total_out_edges=len(out_edges),
        )

    # ------------------------------------------------------------------
    # Graph statistics
    # ------------------------------------------------------------------

    @property
    def node_count(self) -> int:
        return self._g.number_of_nodes()

    @property
    def edge_count(self) -> int:
        return self._g.number_of_edges()

    def relationship_counts(self) -> dict[str, int]:
        counts: dict[str, int] = defaultdict(int)
        for edge in self.all_edges():
            counts[edge.relationship_type.value] += 1
        return dict(sorted(counts.items(), key=lambda x: -x[1]))

    def isolated_nodes(self) -> list[str]:
        return [n for n in self._g.nodes if self._g.degree(n) == 0]

    # ------------------------------------------------------------------
    # Expose the raw nx graph for algorithms that need it
    # ------------------------------------------------------------------

    @property
    def nx_graph(self) -> nx.MultiDiGraph:
        return self._g

    def to_undirected(self) -> nx.Graph:
        """Weighted undirected view — used for community detection."""
        ug = nx.Graph()
        for u, v, k, d in self._g.edges(keys=True, data=True):
            w = d["data"].weight
            if ug.has_edge(u, v):
                ug[u][v]["weight"] = max(ug[u][v]["weight"], w)
            else:
                ug.add_edge(u, v, weight=w)
        return ug
