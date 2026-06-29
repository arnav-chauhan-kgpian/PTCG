"""
Optimizer — orchestrates search strategy over an initial deck.

Uses fast_score during inner loop, full DeckAnalyzer only for final candidates.
"""

from __future__ import annotations

import random

from loguru import logger

from src.cards.relationships.graph import CardGraph
from src.deck_builder.constraints import ConstraintConfig
from src.deck_builder.generators import CardIndex
from src.deck_builder.objectives import ObjectiveSet
from src.deck_builder.repair import RepairEngine
from src.deck_builder.scoring import score_deck_fast
from src.deck_builder.search import get_strategy
from src.decks.analyzer import DeckAnalyzer
from src.decks.models import Deck, DeckSlot


def _slots_to_deck(slots: dict[str, tuple], name: str = "") -> Deck:
    deck_slots = tuple(
        DeckSlot(card=card, count=count)
        for card, count in slots.values()
        if count > 0
    )
    return Deck(name=name, slots=deck_slots)


class Optimizer:
    """
    Wraps a search strategy and applies it to improve an initial deck.

    Inner loop uses fast_score for speed.
    Final candidates are evaluated with the full DeckAnalyzer.
    """

    def __init__(
        self,
        card_index: CardIndex,
        graph: CardGraph,
        analyzer: DeckAnalyzer,
        config: ConstraintConfig | None = None,
        objective_set: ObjectiveSet | None = None,
    ) -> None:
        self._idx = card_index
        self._graph = graph
        self._analyzer = analyzer
        self._cfg = config or ConstraintConfig()
        self._objectives = objective_set or ObjectiveSet()
        self._repair = RepairEngine(card_index, config)

    def optimize(
        self,
        initial_slots: dict[str, tuple],
        strategy_name: str = "beam",
        n_iterations: int = 40,
        beam_width: int = 5,
        n_candidates: int = 5,
        rng: random.Random | None = None,
        deck_name: str = "",
    ) -> list[tuple[dict, float]]:
        """
        Run the chosen search strategy over initial_slots.
        Returns list of (slot_dict, fast_score) sorted best-first.
        Full scoring is done externally by DeckBuilder.
        """
        if rng is None:
            rng = random.Random()

        strategy_fn = get_strategy(strategy_name)

        def fast_scorer(slots: dict) -> float:
            try:
                deck = _slots_to_deck(slots)
                return score_deck_fast(deck)
            except Exception:
                return 0.0

        logger.debug(
            "Optimizer: running '{}' strategy, {} iterations",
            strategy_name, n_iterations,
        )

        results = strategy_fn(
            initial_slots=initial_slots,
            scorer=fast_scorer,
            card_index=self._idx,
            graph=self._graph,
            rng=rng,
            n_iterations=n_iterations,
            beam_width=beam_width,
            repair=self._repair,
        )

        # Deduplicate results
        seen_hashes: set[int] = set()
        unique: list[dict] = []
        for slots in results:
            h = hash(frozenset((k, v[1]) for k, v in slots.items()))
            if h not in seen_hashes:
                seen_hashes.add(h)
                unique.append(slots)

        # Score and sort
        scored: list[tuple[dict, float]] = []
        for slots in unique:
            s = fast_scorer(slots)
            scored.append((slots, s))

        scored.sort(key=lambda x: -x[1])
        return scored[:n_candidates]
