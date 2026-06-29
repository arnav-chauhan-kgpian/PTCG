"""
DeckBuilder — main entry point for Phase 6.

Orchestrates: CardIndex → ConstructiveGenerator → RepairEngine
              → Optimizer → DeckAnalyzer → CandidateDeck ranking
"""

from __future__ import annotations

import random
import time

from loguru import logger

from src.cards.relationships.graph import CardGraph
from src.cards.relationships.traversal import GraphTraversal
from src.cards.types import AnyCard
from src.deck_builder.archetypes import get_template
from src.deck_builder.candidates import BuildResult, CandidateDeck, rank_candidates
from src.deck_builder.constraints import ConstraintConfig
from src.deck_builder.generators import BuildRequest, CardIndex, ConstructiveGenerator
from src.deck_builder.objectives import ObjectiveSet
from src.deck_builder.optimizer import Optimizer, _slots_to_deck
from src.deck_builder.repair import RepairEngine
from src.deck_builder.reports import annotate_candidate
from src.deck_builder.scoring import score_deck_full
from src.decks.analyzer import DeckAnalyzer


class DeckBuilder:
    """
    Production deck construction engine.

    Usage::

        builder = DeckBuilder.from_graph_and_cards(graph, cards)

        # Build around a seed card
        result = builder.build(seed_cards=["Charizard ex"])

        # Build a type-based deck
        result = builder.build(pokemon_type=PokemonType.FIRE)

        # Build by archetype
        result = builder.build(archetype="Control")

        # Improve an existing deck
        result = builder.improve(existing_deck)

        print(exports.to_terminal_build_result(result))
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
        self._traversal = GraphTraversal(graph)
        self._analyzer = analyzer
        self._cfg = config or ConstraintConfig()
        self._objectives = objective_set or ObjectiveSet()
        self._repair = RepairEngine(card_index, self._cfg)
        self._optimizer = Optimizer(
            card_index, graph, analyzer, self._cfg, self._objectives
        )

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_graph_and_cards(
        cls,
        graph: CardGraph,
        cards: list[AnyCard],
        config: ConstraintConfig | None = None,
        objective_weights: dict[str, float] | None = None,
    ) -> DeckBuilder:
        card_index = CardIndex(cards)
        analyzer = DeckAnalyzer(graph)
        obj_set = ObjectiveSet()
        if objective_weights:
            obj_set.apply_weight_overrides(objective_weights)
        return cls(card_index, graph, analyzer, config, obj_set)

    # ------------------------------------------------------------------
    # Main API
    # ------------------------------------------------------------------

    def build(
        self,
        seed_cards: list[str] | None = None,
        pokemon_type=None,
        archetype: str | None = None,
        playstyle: str | None = None,
        n_candidates: int = 5,
        search_strategy: str = "beam",
        max_iterations: int = 40,
        seed: int | None = None,
        objective_weights: dict[str, float] | None = None,
    ) -> BuildResult:
        """Generate n_candidates decks from the given constraints."""
        request = BuildRequest(
            seed_cards=list(seed_cards or []),
            pokemon_type=pokemon_type,
            archetype=archetype,
            playstyle=playstyle,
            n_candidates=n_candidates,
            search_strategy=search_strategy,
            max_iterations=max_iterations,
            seed=seed,
            objective_weights=objective_weights or {},
        )
        return self._execute_build(request)

    def improve(
        self,
        existing_deck,
        n_candidates: int = 5,
        search_strategy: str = "beam",
        max_iterations: int = 50,
        seed: int | None = None,
    ) -> BuildResult:
        """Optimise an existing deck without changing its core identity."""
        slots = {s.card_id: (s.card, s.count) for s in existing_deck.slots}
        request = BuildRequest(
            existing_deck_slots=slots,
            n_candidates=n_candidates,
            search_strategy=search_strategy,
            max_iterations=max_iterations,
            seed=seed,
        )
        return self._execute_build(request)

    def build_from_partial(
        self,
        partial_slots: dict[str, tuple],
        n_candidates: int = 5,
        search_strategy: str = "beam",
        max_iterations: int = 40,
    ) -> BuildResult:
        """Complete a partial deck."""
        request = BuildRequest(
            partial_deck_slots=partial_slots,
            n_candidates=n_candidates,
            search_strategy=search_strategy,
            max_iterations=max_iterations,
        )
        return self._execute_build(request)

    # ------------------------------------------------------------------
    # Internal pipeline
    # ------------------------------------------------------------------

    def _execute_build(self, request: BuildRequest) -> BuildResult:
        t0 = time.perf_counter()
        rng = random.Random(request.seed)

        # Apply objective weight overrides
        if request.objective_weights:
            self._objectives.apply_weight_overrides(request.objective_weights)

        # Apply archetype template to guide construction
        template = get_template(request.archetype or "")

        # Stage A: construct initial deck
        gen = ConstructiveGenerator(
            self._idx, self._graph, self._traversal, self._cfg, rng
        )
        initial_slots = gen.generate(request)

        # Stage B: repair to ensure legality
        repair_result = self._repair.repair(initial_slots)
        repaired_slots = repair_result.slots
        logger.debug(
            "DeckBuilder: initial={} repaired={} (actions: {})",
            sum(c for _, c in initial_slots.values()),
            sum(c for _, c in repaired_slots.values()),
            len(repair_result.actions),
        )

        # Stage C: optimise → get n_candidates slot dicts
        optimized = self._optimizer.optimize(
            repaired_slots,
            strategy_name=request.search_strategy,
            n_iterations=request.max_iterations,
            beam_width=min(request.n_candidates, 5),
            n_candidates=request.n_candidates,
            rng=rng,
            deck_name=self._make_deck_name(request),
        )

        # Ensure we always have at least one candidate
        if not optimized:
            optimized = [(repaired_slots, 0.0)]

        # Stage D: full scoring and annotation
        candidates: list[CandidateDeck] = []
        strategy_names = [request.search_strategy, "hill_climbing", "annealing", "greedy"]

        for i, (slots, _fast_score) in enumerate(optimized):
            try:
                final_slots = self._repair.repair(slots).slots
                deck = _slots_to_deck(final_slots, name=self._make_deck_name(request))
                score, report = score_deck_full(
                    deck, self._analyzer, self._objectives, self._cfg
                )
                strategy = strategy_names[i % len(strategy_names)]
                c = CandidateDeck(
                    deck=deck,
                    score=score,
                    report=report,
                    generation_strategy=strategy,
                )
                c = annotate_candidate(c, request.seed_cards, strategy)
                candidates.append(c)
            except Exception as exc:
                logger.warning("DeckBuilder: candidate {} failed scoring: {}", i, exc)

        ranked = rank_candidates(candidates)
        elapsed = time.perf_counter() - t0
        request_summary = self._describe_request(request)

        logger.info(
            "DeckBuilder: {} candidates in {:.2f}s — best={:.1f}",
            len(ranked), elapsed, ranked[0].score.total if ranked else 0,
        )

        return BuildResult(request_summary=request_summary, candidates=ranked)

    def _make_deck_name(self, request: BuildRequest) -> str:
        if request.seed_cards:
            return f"{request.seed_cards[0]} Deck"
        if request.pokemon_type:
            return f"{request.pokemon_type.name.title()} Deck"
        if request.archetype:
            return f"{request.archetype} Deck"
        return "Generated Deck"

    def _describe_request(self, request: BuildRequest) -> str:
        parts: list[str] = []
        if request.seed_cards:
            parts.append(f"seed={request.seed_cards}")
        if request.pokemon_type:
            parts.append(f"type={request.pokemon_type.name}")
        if request.archetype:
            parts.append(f"archetype={request.archetype}")
        if request.existing_deck_slots:
            parts.append("improve_existing")
        if request.partial_deck_slots:
            parts.append("complete_partial")
        return f"Build({', '.join(parts) or 'random'})"
