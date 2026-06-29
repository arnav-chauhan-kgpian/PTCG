"""
Graph traversal and query API.

All queries are O(degree) or better via NetworkX algorithms.
Results are sorted by edge weight descending for deterministic output.
"""

from __future__ import annotations

import networkx as nx

from src.cards.relationships.graph import CardGraph
from src.cards.relationships.models import (
    DISRUPTION_TYPES,
    SUPPORT_TYPES,
    RelationshipType,
)


class GraphTraversal:
    """High-level query interface over a CardGraph."""

    def __init__(self, graph: CardGraph) -> None:
        self._g = graph

    # ------------------------------------------------------------------
    # Basic accessors
    # ------------------------------------------------------------------

    def neighbors(
        self,
        card_id: str,
        rel: RelationshipType | None = None,
        *,
        include_incoming: bool = False,
    ) -> list[str]:
        """Return card IDs connected to card_id.

        Args:
            card_id: Source card.
            rel:     If given, filter to this relationship type.
            include_incoming: Also include cards that point TO card_id.
        """
        out = {e.target for e in self._g.edges_from(card_id, rel)}
        if include_incoming:
            out |= {e.source for e in self._g.edges_to(card_id, rel)}
        out.discard(card_id)  # remove self-loops from results
        return sorted(out)

    def weighted_neighbors(
        self,
        card_id: str,
        rel: RelationshipType | None = None,
    ) -> list[tuple[str, float]]:
        """Return (card_id, weight) pairs sorted by weight descending."""
        edges = self._g.edges_from(card_id, rel)
        seen: dict[str, float] = {}
        for e in edges:
            if e.target == card_id:
                continue
            if e.target not in seen or e.weight > seen[e.target]:
                seen[e.target] = e.weight
        return sorted(seen.items(), key=lambda x: -x[1])

    def shortest_path(
        self,
        source: str,
        target: str,
    ) -> list[str] | None:
        """Shortest path between two cards (ignores edge direction for flexibility)."""
        try:
            ug = self._g.to_undirected()
            path = nx.shortest_path(ug, source, target)
            return path
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None

    def shortest_path_length(self, source: str, target: str) -> int | None:
        path = self.shortest_path(source, target)
        return len(path) - 1 if path else None

    # ------------------------------------------------------------------
    # Typed queries
    # ------------------------------------------------------------------

    def find_support_cards(
        self,
        card_id: str,
        *,
        top_n: int = 10,
    ) -> list[str]:
        """Cards that support card_id (incoming SUPPORT_TYPES edges)."""
        edges = self._g.edges_to(card_id)
        edges = [e for e in edges if e.relationship_type in SUPPORT_TYPES and e.source != card_id]
        seen: dict[str, float] = {}
        for e in edges:
            if e.source not in seen or e.weight > seen[e.source]:
                seen[e.source] = e.weight
        return [cid for cid, _ in sorted(seen.items(), key=lambda x: -x[1])[:top_n]]

    def find_counters(
        self,
        card_id: str,
        *,
        top_n: int = 10,
    ) -> list[str]:
        """Cards that counter card_id."""
        edges = self._g.edges_to(card_id)
        edges = [e for e in edges if e.relationship_type in DISRUPTION_TYPES and e.source != card_id]
        seen: dict[str, float] = {}
        for e in edges:
            if e.source not in seen or e.weight > seen[e.source]:
                seen[e.source] = e.weight
        return [cid for cid, _ in sorted(seen.items(), key=lambda x: -x[1])[:top_n]]

    def find_energy_package(
        self,
        card_id: str,
    ) -> list[str]:
        """Energy cards compatible with card_id."""
        energy_rels = {RelationshipType.USES_ENERGY, RelationshipType.ENERGY_SYNERGY}
        edges = [e for e in self._g.edges_from(card_id) if e.relationship_type in energy_rels]
        return [e.target for e in sorted(edges, key=lambda x: -x.weight) if e.target != card_id]

    def find_draw_engine(
        self,
        card_id: str,
        *,
        top_n: int = 5,
    ) -> list[str]:
        """Trainer cards in the graph that are draw engines."""
        # Draw engine trainers: nodes with self-loop DRAW_ENGINE
        draw_ids: list[str] = []
        for node in self._g.all_nodes():
            if self._g.has_edge(node.card_id, node.card_id, RelationshipType.DRAW_ENGINE):
                draw_ids.append(node.card_id)
        return draw_ids[:top_n]

    def recommend_partners(
        self,
        card_id: str,
        *,
        top_n: int = 10,
    ) -> list[str]:
        """Top synergy partners for card_id, sorted by combined edge weight."""
        synergy_rels = (
            RelationshipType.BENCH_SUPPORT,
            RelationshipType.DRAW_ENGINE,
            RelationshipType.DAMAGE_BOOST,
            RelationshipType.TYPE_SYNERGY,
            RelationshipType.ENERGY_SYNERGY,
            RelationshipType.HEALS,
            RelationshipType.SEARCHES_FOR,
            RelationshipType.ACCELERATES_ENERGY,
            RelationshipType.ABILITY_SUPPORT,
            RelationshipType.CONSISTENCY,
        )
        scored: dict[str, float] = {}
        for e in self._g.edges_from(card_id):
            if e.relationship_type not in synergy_rels or e.target == card_id:
                continue
            scored[e.target] = scored.get(e.target, 0.0) + e.weight
        for e in self._g.edges_to(card_id):
            if e.relationship_type not in synergy_rels or e.source == card_id:
                continue
            scored[e.source] = scored.get(e.source, 0.0) + e.weight * 0.8
        return [cid for cid, _ in sorted(scored.items(), key=lambda x: -x[1])[:top_n]]

    def recommend_replacements(
        self,
        card_id: str,
        *,
        top_n: int = 5,
    ) -> list[str]:
        """Cards with similar roles to card_id (same type + similar degree)."""
        node = self._g.node(card_id)
        if node is None:
            return []
        same_type = [
            n for n in self._g.all_nodes()
            if n.card_super_type == node.card_super_type
            and n.card_id != card_id
            and n.pokemon_type == node.pokemon_type
            and n.stage == node.stage
        ]
        return [n.card_id for n in same_type[:top_n]]

    def recommend_finishers(
        self,
        card_id: str,
        *,
        top_n: int = 5,
    ) -> list[str]:
        """Cards tagged as finishers that partner with card_id."""
        finisher_ids = [
            n.card_id for n in self._g.all_nodes()
            if self._g.has_edge(n.card_id, n.card_id, RelationshipType.FINISHER)
        ]
        partners = set(self.recommend_partners(card_id, top_n=50))
        overlap = [fid for fid in finisher_ids if fid in partners]
        return (overlap + finisher_ids)[:top_n]

    def recommend_openers(
        self,
        card_id: str,
        *,
        top_n: int = 5,
    ) -> list[str]:
        """Basic Pokémon that work well with card_id."""
        from src.cards.enums import Stage
        basics = [
            n.card_id for n in self._g.all_nodes()
            if n.stage == Stage.BASIC and n.card_id != card_id
        ]
        partners = set(self.recommend_partners(card_id, top_n=50))
        overlap = [b for b in basics if b in partners]
        return (overlap + basics)[:top_n]

    def recommend_consistency_cards(
        self,
        card_id: str,
        *,
        top_n: int = 5,
    ) -> list[str]:
        """Draw / search / consistency trainers relevant to card_id."""
        consistency_ids = [
            n.card_id for n in self._g.all_nodes()
            if self._g.has_edge(n.card_id, n.card_id, RelationshipType.CONSISTENCY)
            or self._g.has_edge(n.card_id, n.card_id, RelationshipType.DRAW_ENGINE)
        ]
        return consistency_ids[:top_n]

    def recommend_disruption(
        self,
        card_id: str,
        *,
        top_n: int = 5,
    ) -> list[str]:
        """Counter / disruption cards useful in a deck featuring card_id."""
        disruption_ids = [
            n.card_id for n in self._g.all_nodes()
            if any(self._g.has_edge(n.card_id, n.card_id, rel) for rel in DISRUPTION_TYPES)
            and n.card_id != card_id
        ]
        return disruption_ids[:top_n]

    def related_cards(
        self,
        card_id: str,
        *,
        top_n: int = 20,
    ) -> list[str]:
        """All cards related to card_id in any way, sorted by total edge weight."""
        scored: dict[str, float] = {}
        for e in self._g.edges_from(card_id):
            if e.target == card_id:
                continue
            scored[e.target] = scored.get(e.target, 0.0) + e.weight
        for e in self._g.edges_to(card_id):
            if e.source == card_id:
                continue
            scored[e.source] = scored.get(e.source, 0.0) + e.weight * 0.6
        return [cid for cid, _ in sorted(scored.items(), key=lambda x: -x[1])[:top_n]]

    def similar_cards(
        self,
        card_id: str,
        *,
        top_n: int = 10,
    ) -> list[str]:
        """Structurally similar cards (same card_super_type, similar profile)."""
        node = self._g.node(card_id)
        if node is None:
            return []
        candidates = [
            n for n in self._g.all_nodes()
            if n.card_super_type == node.card_super_type
            and n.card_id != card_id
        ]
        if node.pokemon_type:
            candidates = [c for c in candidates if c.pokemon_type == node.pokemon_type] or candidates
        return [c.card_id for c in candidates[:top_n]]

    def evolution_chain(self, card_id: str) -> list[str]:
        """Full evolution chain containing card_id, from Basic to final form."""
        # Walk backwards to find the root (Basic Pokémon)
        visited_back: set[str] = set()
        chain: list[str] = []

        def walk_back(cid: str) -> None:
            if cid in visited_back:
                return
            visited_back.add(cid)
            for e in self._g.edges_from(cid, RelationshipType.EVOLVES_FROM):
                walk_back(e.target)
            chain.append(cid)

        walk_back(card_id)

        # chain is now [root, ..., card_id] (Basic first due to append order)
        # Walk forward from EVERY node in chain to find later evolutions
        seen_forward: set[str] = set(chain)

        def walk_forward(cid: str) -> None:
            for e in self._g.edges_from(cid, RelationshipType.EVOLVES_TO):
                if e.target not in seen_forward:
                    seen_forward.add(e.target)
                    chain.append(e.target)
                    walk_forward(e.target)

        # Must walk forward from all nodes already in the chain
        for cid in list(chain):
            walk_forward(cid)

        return chain
