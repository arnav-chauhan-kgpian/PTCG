"""
Search strategies — modular optimisation backends.

All strategies share the same interface:
    search(initial_slots, scorer, card_index, graph, rng, **kwargs)
        → list[dict]  (ranked best-to-last slot dicts)

`scorer` is a callable that takes a slot dict and returns float (higher = better).
Strategies never call DeckAnalyzer directly — scoring is injected.
"""

from __future__ import annotations

import math
import random
from collections.abc import Callable
from typing import TYPE_CHECKING

from src.deck_builder.mutations import random_mutation
from src.deck_builder.repair import RepairEngine

if TYPE_CHECKING:
    from src.cards.relationships.graph import CardGraph
    from src.deck_builder.generators import CardIndex

Scorer = Callable[[dict], float]


# ---------------------------------------------------------------------------
# Greedy (single-pass constructive — effectively a no-op in search phase)
# ---------------------------------------------------------------------------

def greedy_search(
    initial_slots: dict,
    scorer: Scorer,
    card_index: CardIndex,
    graph: CardGraph,
    rng: random.Random,
    n_iterations: int = 1,
    **_,
) -> list[dict]:
    """Return the initial deck unchanged (construction is done upstream)."""
    return [initial_slots]


# ---------------------------------------------------------------------------
# Hill Climbing
# ---------------------------------------------------------------------------

def hill_climbing(
    initial_slots: dict,
    scorer: Scorer,
    card_index: CardIndex,
    graph: CardGraph,
    rng: random.Random,
    n_iterations: int = 60,
    repair: RepairEngine | None = None,
    **_,
) -> list[dict]:
    current = dict(initial_slots)
    current_score = scorer(current)
    history = [current]

    for _ in range(n_iterations):
        result = random_mutation(current, card_index, graph, rng)
        if not result.success:
            continue
        candidate = result.slots
        if repair:
            candidate = repair.repair(candidate).slots
        s = scorer(candidate)
        if s >= current_score:
            current = candidate
            current_score = s
            history.append(current)

    return [history[-1]] if history else [initial_slots]


# ---------------------------------------------------------------------------
# Simulated Annealing
# ---------------------------------------------------------------------------

def simulated_annealing(
    initial_slots: dict,
    scorer: Scorer,
    card_index: CardIndex,
    graph: CardGraph,
    rng: random.Random,
    n_iterations: int = 120,
    t_start: float = 10.0,
    t_end: float = 0.1,
    repair: RepairEngine | None = None,
    **_,
) -> list[dict]:
    current = dict(initial_slots)
    current_score = scorer(current)
    best = current
    best_score = current_score

    cooling = (t_end / t_start) ** (1.0 / max(n_iterations, 1))
    temp = t_start

    for _ in range(n_iterations):
        result = random_mutation(current, card_index, graph, rng)
        if not result.success:
            temp *= cooling
            continue
        candidate = result.slots
        if repair:
            candidate = repair.repair(candidate).slots
        s = scorer(candidate)
        delta = s - current_score

        if delta >= 0 or rng.random() < math.exp(delta / max(temp, 1e-9)):
            current = candidate
            current_score = s
            if s > best_score:
                best = candidate
                best_score = s

        temp *= cooling

    return [best]


# ---------------------------------------------------------------------------
# Beam Search (over mutation space)
# ---------------------------------------------------------------------------

def beam_search(
    initial_slots: dict,
    scorer: Scorer,
    card_index: CardIndex,
    graph: CardGraph,
    rng: random.Random,
    n_iterations: int = 30,
    beam_width: int = 5,
    repair: RepairEngine | None = None,
    **_,
) -> list[dict]:
    beam: list[tuple[float, dict]] = [(scorer(initial_slots), initial_slots)]

    for _ in range(n_iterations):
        candidates: list[tuple[float, dict]] = list(beam)

        for _, slots in beam:
            for _attempt in range(beam_width * 2):
                result = random_mutation(slots, card_index, graph, rng)
                if not result.success:
                    continue
                cand = result.slots
                if repair:
                    cand = repair.repair(cand).slots
                s = scorer(cand)
                candidates.append((s, cand))

        # Keep top beam_width unique decks by score
        candidates.sort(key=lambda x: -x[0])
        seen: list[tuple[float, dict]] = []
        seen_hashes: set[int] = set()
        for s, slots in candidates:
            h = hash(frozenset((k, v[1]) for k, v in slots.items()))
            if h not in seen_hashes:
                seen.append((s, slots))
                seen_hashes.add(h)
            if len(seen) >= beam_width:
                break
        beam = seen

    return [slots for _, slots in beam]


# ---------------------------------------------------------------------------
# Random Restart
# ---------------------------------------------------------------------------

def random_restart(
    initial_slots: dict,
    scorer: Scorer,
    card_index: CardIndex,
    graph: CardGraph,
    rng: random.Random,
    n_iterations: int = 5,
    inner_strategy: str = "hill_climbing",
    inner_iterations: int = 40,
    repair: RepairEngine | None = None,
    **_,
) -> list[dict]:
    all_results: list[tuple[float, dict]] = []

    for restart in range(n_iterations):
        # Diversify initial deck slightly for each restart
        diversified = _randomise_start(initial_slots, card_index, rng, strength=restart)

        if inner_strategy == "annealing":
            results = simulated_annealing(
                diversified, scorer, card_index, graph, rng,
                n_iterations=inner_iterations, repair=repair,
            )
        else:
            results = hill_climbing(
                diversified, scorer, card_index, graph, rng,
                n_iterations=inner_iterations, repair=repair,
            )

        for slots in results:
            all_results.append((scorer(slots), slots))

    all_results.sort(key=lambda x: -x[0])
    return [slots for _, slots in all_results[:n_iterations]] or [initial_slots]


def _randomise_start(
    slots: dict,
    card_index: CardIndex,
    rng: random.Random,
    strength: int = 1,
) -> dict:
    """Apply `strength` random swaps to diversify a starting point."""
    from src.deck_builder.mutations import swap_card
    # Fake graph — swap_card doesn't need graph
    s = dict(slots)
    for _ in range(strength * 3):
        result = swap_card(s, card_index, rng)
        if result.success:
            s = result.slots
    return s


# ---------------------------------------------------------------------------
# Strategy registry
# ---------------------------------------------------------------------------

STRATEGIES = {
    "greedy": greedy_search,
    "hill_climbing": hill_climbing,
    "annealing": simulated_annealing,
    "beam": beam_search,
    "random_restart": random_restart,
}


def get_strategy(name: str) -> Callable:
    if name not in STRATEGIES:
        raise ValueError(f"Unknown search strategy '{name}'. Choose from: {list(STRATEGIES)}")
    return STRATEGIES[name]
