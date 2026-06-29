"""
Card Relationship & Synergy Engine.

Public API::

    from src.cards.relationships import build_graph, CardGraph, GraphTraversal

    graph = build_graph(cards)
    traversal = GraphTraversal(graph)

    partners = traversal.recommend_partners("1001")
    chain = traversal.evolution_chain("1023")
    profile = graph.profile("1001")
"""

from src.cards.relationships import exports
from src.cards.relationships.builder import GraphBuilder
from src.cards.relationships.clustering import detect_communities
from src.cards.relationships.graph import CardGraph
from src.cards.relationships.models import (
    CardEdge,
    CardNode,
    CardProfile,
    Community,
    RelationshipType,
)
from src.cards.relationships.scoring import rank_edges, score_edge
from src.cards.relationships.traversal import GraphTraversal
from src.cards.relationships.validators import GraphValidationReport, GraphValidator


def build_graph(cards: list) -> CardGraph:
    """Convenience one-liner: build the full CardGraph from a card list."""
    return GraphBuilder().build(cards)


__all__ = [
    "build_graph",
    "CardEdge",
    "CardNode",
    "CardProfile",
    "CardGraph",
    "Community",
    "RelationshipType",
    "GraphBuilder",
    "GraphTraversal",
    "detect_communities",
    "GraphValidator",
    "GraphValidationReport",
    "score_edge",
    "rank_edges",
    "exports",
]
