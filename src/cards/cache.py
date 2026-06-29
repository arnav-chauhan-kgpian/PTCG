"""
Lightweight in-process caching for the card repository.

Uses functools.lru_cache and slot-based dictionaries to avoid repeated
allocations during high-frequency self-play lookups.

Design:
  - CardIndex: pre-built lookup tables constructed once at load time.
  - All index structures are plain Python dicts/lists for minimum overhead.
  - No external dependencies (Redis, SQLite, etc.) — everything lives in RAM.
  - Thread-safe for reads (Python GIL protects dict reads on CPython).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import TypeVar

from src.cards.enums import EnergyType, ExpansionCode, PokemonType, Stage, TrainerType
from src.cards.models import Card, EnergyCard, PokemonCard, TrainerCard

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Index
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class CardIndex:
    """All pre-computed indexes over the card list.

    Built once at repository initialisation; never mutated after that.
    Accessing any field is O(1) dict lookup.
    """

    # Primary index
    by_id: dict[int, Card] = field(default_factory=dict)

    # Name → list (handles variant reprints sharing a name)
    by_name: dict[str, list[Card]] = field(default_factory=lambda: defaultdict(list))

    # Lower-cased name → list (for case-insensitive lookups)
    by_name_lower: dict[str, list[Card]] = field(default_factory=lambda: defaultdict(list))

    # Type → Pokémon cards
    by_type: dict[PokemonType, list[PokemonCard]] = field(
        default_factory=lambda: defaultdict(list)
    )

    # Stage → Pokémon cards
    by_stage: dict[Stage, list[PokemonCard]] = field(
        default_factory=lambda: defaultdict(list)
    )

    # Expansion → cards
    by_expansion: dict[ExpansionCode, list[Card]] = field(
        default_factory=lambda: defaultdict(list)
    )

    # TrainerType → trainer cards
    by_trainer_type: dict[TrainerType, list[TrainerCard]] = field(
        default_factory=lambda: defaultdict(list)
    )

    # EnergyType → energy cards
    by_energy_type: dict[EnergyType, list[EnergyCard]] = field(
        default_factory=lambda: defaultdict(list)
    )

    # HP → Pokémon cards
    by_hp: dict[int, list[PokemonCard]] = field(
        default_factory=lambda: defaultdict(list)
    )

    # All names list (for fuzzy search candidates)
    all_names: list[str] = field(default_factory=list)


def build_index(cards: Sequence[Card]) -> CardIndex:
    """Build all indexes from a flat card list. O(n) time and space."""
    idx = CardIndex()

    for card in cards:
        idx.by_id[card.card_id] = card
        idx.by_name[card.name].append(card)
        idx.by_name_lower[card.name.lower()].append(card)
        idx.by_expansion[card.expansion].append(card)
        idx.all_names.append(card.name)

        if isinstance(card, PokemonCard):
            idx.by_type[card.pokemon_type].append(card)
            idx.by_stage[card.stage].append(card)
            idx.by_hp[card.hp].append(card)

        elif isinstance(card, TrainerCard):
            idx.by_trainer_type[card.trainer_type].append(card)

        elif isinstance(card, EnergyCard):
            idx.by_energy_type[card.energy_type].append(card)

    return idx
