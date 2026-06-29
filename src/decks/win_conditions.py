"""
Win condition inference.

Identifies primary/secondary win conditions, finishers, core engine,
critical cards, and dependency chains — without simulating games.
"""

from __future__ import annotations

from collections import defaultdict

from pydantic import BaseModel, ConfigDict

from src.cards.enums import Stage
from src.cards.models import PokemonCard
from src.cards.relationships.graph import CardGraph
from src.cards.relationships.models import RelationshipType
from src.decks.metrics import DeckMetrics
from src.decks.models import Deck


class WinConditionReport(BaseModel):
    """Structured win condition analysis."""

    model_config = ConfigDict(frozen=True)

    primary_win_condition: str
    secondary_win_condition: str | None
    fallback_strategy: str

    finishers: tuple[str, ...]         # card names (highest damage / prize closers)
    core_engine: tuple[str, ...]       # cards the deck revolves around
    supporting_engine: tuple[str, ...]  # support cards for the engine
    critical_cards: tuple[str, ...]    # cards whose absence breaks the strategy

    dependency_chains: tuple[str, ...]  # e.g. "Ralts → Kirlia → Gardevoir ex"

    expected_prize_turns: float        # rough estimate of how many turns to close


def _infer_primary_win(deck: Deck, metrics: DeckMetrics) -> str:
    """Infer primary win condition from card data."""
    if metrics.max_damage >= 250:
        return "One-shot KO — high-damage attacker takes 2+ prizes in a single attack"
    if metrics.max_damage >= 150:
        return "Two-hit KO — consistent damage stream to take prizes efficiently"
    if metrics.disruption_score >= 12 and metrics.max_damage < 100:
        return "Deck-out — disrupt opponent's resources until they deck out"
    if metrics.healing_score >= 8 and metrics.disruption_score >= 6:
        return "Stall — outlast opponent by recycling resources indefinitely"
    if metrics.energy_acceleration >= 6 and metrics.energy_count >= 15:
        return "Energy burst — accelerate to overwhelming attacks ahead of schedule"
    if metrics.stage2_count >= 4:
        return "Evolution ramp — establish Stage 2 engine for sustained power"
    return "Prize race — steady damage to take six prizes before opponent"


def _infer_secondary_win(deck: Deck, metrics: DeckMetrics) -> str | None:
    if metrics.disruption_score >= 8:
        return "Hand disruption fallback — force opponent into dead hands"
    if metrics.recovery_score >= 6:
        return "Resource loop — recycle attackers to outlast prize race"
    if metrics.healing_score >= 5:
        return "Healing stall — buy extra turns when threatened"
    return None


def _find_finishers(deck: Deck, graph: CardGraph) -> list[str]:
    """Cards tagged as FINISHER or with highest base damage."""
    finisher_names: list[str] = []
    damage_ranking: list[tuple[int, str]] = []

    for slot in deck.pokemon_slots():
        card = slot.card
        if not isinstance(card, PokemonCard):
            continue
        cid = str(card.card_id)
        if graph.has_edge(cid, cid, RelationshipType.FINISHER):
            finisher_names.append(card.name)
        max_dmg = max((a.damage.base for a in card.attacks), default=0)
        if max_dmg > 0:
            damage_ranking.append((max_dmg, card.name))

    if not finisher_names:
        damage_ranking.sort(reverse=True)
        finisher_names = [name for _, name in damage_ranking[:3]]

    return finisher_names[:5]


def _find_core_engine(deck: Deck, graph: CardGraph) -> list[str]:
    """Cards with highest combined internal + external graph degree."""
    deck_ids = deck.unique_card_ids()
    id_to_name = {s.card_id: s.name for s in deck.slots}

    scored: dict[str, float] = {}
    for card_id in deck_ids:
        internal = sum(
            1 for e in graph.edges_from(card_id)
            if e.target in deck_ids and e.target != card_id
        )
        profile = graph.profile(card_id)
        ext = profile.total_out_edges if profile else 0
        scored[card_id] = internal * 2.0 + ext * 0.1

    top = sorted(scored.items(), key=lambda x: -x[1])[:5]
    return [id_to_name.get(cid, cid) for cid, _ in top]


def _find_evolution_chains(deck: Deck) -> list[str]:
    """Detect evolution chains present in the deck."""
    names_in_deck: set[str] = {s.card.name for s in deck.pokemon_slots()}
    chains: list[str] = []

    # Walk evolution links
    visited: set[str] = set()
    for slot in deck.pokemon_slots():
        card = slot.card
        if not isinstance(card, PokemonCard):
            continue
        if card.stage != Stage.STAGE_2:
            continue
        if card.name in visited:
            continue
        visited.add(card.name)
        # Try to build chain
        chain = [card.name]
        prev = card.previous_stage
        while prev and prev in names_in_deck:
            chain.insert(0, prev)
            # Find the prev card
            prev_card = next(
                (s.card for s in deck.pokemon_slots()
                 if s.card.name == prev and isinstance(s.card, PokemonCard)),
                None,
            )
            if prev_card and isinstance(prev_card, PokemonCard):
                prev = prev_card.previous_stage
            else:
                break
        if len(chain) > 1:
            chains.append(" → ".join(chain))

    return chains


def _estimate_prize_turns(metrics: DeckMetrics) -> float:
    """Rough estimate of turns to close game."""
    if metrics.max_damage == 0:
        return 999.0
    # Average HP of opponent's Pokémon assumed ~150
    assumed_hp = 150
    hits_to_ko = math.ceil(assumed_hp / max(metrics.avg_damage, 1)) if metrics.avg_damage > 0 else 3
    # 6 prizes, assume 2 prizes per multi-prize KO or 1 per single
    prize_model_factor = 2.0 if metrics.rule_box_count > metrics.pokemon_count / 2 else 1.2
    turns = (6 / prize_model_factor) * hits_to_ko
    # Add setup turns
    setup = 1 if metrics.stage2_count == 0 else 2 if metrics.stage1_count > 0 else 3
    return round(turns + setup, 1)


import math


def compute_win_conditions(deck: Deck, metrics: DeckMetrics, graph: CardGraph) -> WinConditionReport:
    primary = _infer_primary_win(deck, metrics)
    secondary = _infer_secondary_win(deck, metrics)
    finishers = _find_finishers(deck, graph)
    core_engine = _find_core_engine(deck, graph)

    # Supporting engine: trainer cards in core engine region
    supporting = [
        s.name for s in deck.trainer_slots()
        if s.name not in core_engine
    ][:5]

    # Critical cards: those with highest in-deck dependency count
    dep_count: dict[str, int] = defaultdict(int)
    deck_ids = deck.unique_card_ids()
    for card_id in deck_ids:
        profile = graph.profile(card_id)
        if profile is None:
            continue
        for req in profile.requires:
            if req in deck_ids:
                dep_count[req] += 1

    id_to_name = {s.card_id: s.name for s in deck.slots}
    critical = [
        id_to_name.get(cid, cid)
        for cid, _ in sorted(dep_count.items(), key=lambda x: -x[1])[:5]
    ]

    chains = _find_evolution_chains(deck)
    prize_turns = _estimate_prize_turns(metrics)

    fallback = "Conserve resources and switch to available attackers"
    if metrics.recovery_score >= 4:
        fallback = "Retrieve KO'd attackers from discard and continue prize race"
    elif metrics.healing_score >= 4:
        fallback = "Heal active attacker to extend its effective lifespan"

    return WinConditionReport(
        primary_win_condition=primary,
        secondary_win_condition=secondary,
        fallback_strategy=fallback,
        finishers=tuple(finishers),
        core_engine=tuple(core_engine),
        supporting_engine=tuple(supporting),
        critical_cards=tuple(critical),
        dependency_chains=tuple(chains),
        expected_prize_turns=prize_turns,
    )
