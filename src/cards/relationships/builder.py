"""
GraphBuilder — assembles the complete CardGraph from a card collection.

Usage::

    from src.cards.repository import load_repository
    from src.cards.relationships.builder import GraphBuilder

    repo = load_repository(...)
    graph = GraphBuilder().build(list(repo.all()))
"""

from __future__ import annotations

import time
from collections.abc import Callable

from loguru import logger

from src.cards.models import EnergyCard, PokemonCard, TrainerCard
from src.cards.relationships.analyzers import (
    EffectAnalyzer,
    EnergyAnalyzer,
    EvolutionAnalyzer,
    TextReferenceAnalyzer,
    TrainerRoleAnalyzer,
    TypeSynergyAnalyzer,
)
from src.cards.relationships.edges import merge_edges
from src.cards.relationships.graph import CardGraph
from src.cards.relationships.models import CardEdge, CardNode
from src.cards.types import AnyCard


def _card_id(card: AnyCard) -> str:
    return str(card.card_id)


def _build_node(card: AnyCard) -> CardNode:
    """Extract a CardNode from any card type."""
    base = {
        "card_id": _card_id(card),
        "name": card.name,
        "card_super_type": card.card_super_type,
    }
    if isinstance(card, PokemonCard):
        base["pokemon_type"] = card.pokemon_type
        base["stage"] = card.stage
        base["hp"] = card.hp
        base["retreat_cost"] = card.retreat_cost
        # Collect all effect texts into one string for graph node storage
        texts = []
        if card.ability:
            texts.append(card.ability.effect)
        if card.tera_ability:
            texts.append(card.tera_ability.effect)
        for atk in card.attacks:
            texts.append(atk.effect)
        base["effect_text"] = " ".join(texts)
    elif isinstance(card, TrainerCard):
        base["trainer_type"] = card.trainer_type
        base["effect_text"] = card.effect
    elif isinstance(card, EnergyCard):
        base["energy_type"] = card.energy_type
        base["provides"] = card.provides
        base["effect_text"] = card.effect
    return CardNode(**base)


class GraphBuilder:
    """Builds a CardGraph from a collection of cards.

    Custom analyzers can be added via ``add_analyzer()``.
    """

    def __init__(self) -> None:
        self._analyzers: list[Callable[[list[AnyCard]], list[CardEdge]]] = [
            EvolutionAnalyzer().analyze,
            EffectAnalyzer().analyze,
            EnergyAnalyzer().analyze,
            TrainerRoleAnalyzer().analyze,
            TypeSynergyAnalyzer().analyze,
            TextReferenceAnalyzer().analyze,
        ]

    def add_analyzer(
        self,
        fn: Callable[[list[AnyCard]], list[CardEdge]],
    ) -> None:
        """Register an extra edge-extraction function."""
        self._analyzers.append(fn)

    def build(self, cards: list[AnyCard]) -> CardGraph:
        t0 = time.perf_counter()
        graph = CardGraph()

        # 1. Add all nodes
        for card in cards:
            try:
                graph.add_node(_build_node(card))
            except Exception as exc:
                logger.warning("Failed to build node for card {}: {}", card.card_id, exc)

        logger.info("GraphBuilder: {} nodes added", graph.node_count)

        # 2. Run all analyzers
        all_edges: list[CardEdge] = []
        for analyzer_fn in self._analyzers:
            try:
                result = analyzer_fn(cards)
                all_edges.extend(result)
                logger.debug("Analyzer {} produced {} edges", analyzer_fn.__qualname__, len(result))
            except Exception as exc:
                logger.error("Analyzer {} failed: {}", analyzer_fn.__qualname__, exc)

        # 3. Merge duplicates
        merged = merge_edges(all_edges)
        logger.info("GraphBuilder: {} raw edges → {} merged", len(all_edges), len(merged))

        # 4. Filter edges whose nodes exist in the graph
        valid_edges = [
            e for e in merged
            if graph.has_node(e.source) and graph.has_node(e.target)
        ]
        skipped = len(merged) - len(valid_edges)
        if skipped:
            logger.warning("GraphBuilder: {} edges skipped (missing node reference)", skipped)

        # 5. Add edges
        graph.add_edges(valid_edges)

        # 6. Finalise
        graph.finalise()
        elapsed = time.perf_counter() - t0
        logger.info("CardGraph built in {:.2f}s", elapsed)
        return graph
