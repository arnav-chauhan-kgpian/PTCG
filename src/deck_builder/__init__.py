"""
Automatic Deck Construction Engine — public API.

Usage::

    from src.deck_builder import DeckBuilder, exports
    from src.cards.enums import PokemonType

    builder = DeckBuilder.from_graph_and_cards(graph, cards)
    result = builder.build(seed_cards=["Charizard ex"], n_candidates=5)

    print(exports.to_terminal_build_result(result))
    for c in result.ranked():
        print(exports.to_ptcg_live(c))
"""

from src.deck_builder import exports
from src.deck_builder.archetypes import TEMPLATES, ArchetypeTemplate, get_template
from src.deck_builder.builder import DeckBuilder
from src.deck_builder.candidates import BuildResult, CandidateDeck, rank_candidates
from src.deck_builder.constraints import ConstraintConfig, ConstraintViolation
from src.deck_builder.generators import BuildRequest, CardIndex, ConstructiveGenerator
from src.deck_builder.objectives import (
    DEFAULT_OBJECTIVES,
    ConsistencyObjective,
    DamageCeilingObjective,
    DrawEngineObjective,
    EnergyCurveObjective,
    EvolutionObjective,
    ObjectiveSet,
    PrizeLiabilityObjective,
    RecoveryObjective,
    SearchEngineObjective,
    SynergyObjective,
)
from src.deck_builder.optimizer import Optimizer
from src.deck_builder.repair import RepairAction, RepairEngine, RepairResult
from src.deck_builder.scoring import CandidateScore, score_deck_fast, score_deck_full
from src.deck_builder.search import STRATEGIES, get_strategy

__all__ = [
    "DeckBuilder",
    "BuildRequest",
    "BuildResult",
    "CandidateDeck",
    "CandidateScore",
    "CardIndex",
    "ConstructiveGenerator",
    "ObjectiveSet",
    "DEFAULT_OBJECTIVES",
    "ConsistencyObjective",
    "SynergyObjective",
    "EnergyCurveObjective",
    "DrawEngineObjective",
    "SearchEngineObjective",
    "EvolutionObjective",
    "DamageCeilingObjective",
    "PrizeLiabilityObjective",
    "RecoveryObjective",
    "Optimizer",
    "RepairEngine",
    "RepairAction",
    "RepairResult",
    "ConstraintConfig",
    "ConstraintViolation",
    "ArchetypeTemplate",
    "TEMPLATES",
    "get_template",
    "get_strategy",
    "STRATEGIES",
    "score_deck_fast",
    "score_deck_full",
    "rank_candidates",
    "exports",
]
