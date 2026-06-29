"""
CardRepository — the single public entry point for card lookups.

Design goals:
  1. Load once, query millions of times with zero I/O overhead.
  2. Every query method returns typed results (no raw dicts).
  3. Filtering composes cleanly: callers can chain results.
  4. Fuzzy name search is built in.

Usage::

    from src.cards import load_repository

    repo = load_repository("EN_Card_Data.csv")

    charizard = repo.get_by_name("Charizard ex")
    fire_pokemon = repo.by_type(PokemonType.FIRE)
    results = repo.search("Charzard")   # typo-tolerant
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from loguru import logger

from src.cards.cache import CardIndex, build_index
from src.cards.enums import (
    CardCategory,
    EnergyType,
    ExpansionCode,
    PokemonType,
    RuleBox,
    Stage,
    TrainerType,
)
from src.cards.exceptions import CardNotFoundError
from src.cards.models import Card, EnergyCard, PokemonCard, TrainerCard
from src.cards.parser import ParseResult, parse_csv
from src.cards.search import search_by_name, search_contains, search_effect_text
from src.cards.validators import ValidationReport, validate_cards


class CardRepository:
    """Immutable, indexed card database.

    Construct via ``CardRepository.from_csv(path)`` or the convenience
    wrapper ``load_repository(path)``.

    After construction the repository is read-only.  All query methods
    return new list objects; the internal indexes are never exposed.
    """

    def __init__(self, parse_result: ParseResult, *, run_validation: bool = True) -> None:
        self._cards: list[Card] = parse_result.cards
        self._parse_errors = parse_result.errors
        self._parse_warnings = parse_result.warnings
        self._index: CardIndex = build_index(self._cards)

        self._validation: ValidationReport | None = None
        if run_validation:
            self._validation = validate_cards(self._cards)

        logger.info(
            "CardRepository ready: {} cards indexed ({} errors during parse)",
            len(self._cards),
            len(self._parse_errors),
        )

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def from_csv(
        cls,
        path: str | Path,
        *,
        run_validation: bool = True,
    ) -> CardRepository:
        """Parse *path* and return a fully initialised repository."""
        result = parse_csv(path)
        return cls(result, run_validation=run_validation)

    # ------------------------------------------------------------------
    # Primary lookups
    # ------------------------------------------------------------------

    def get_by_id(self, card_id: int) -> Card:
        """Return the card with the given ID.

        Raises:
            CardNotFoundError: if no card with that ID exists.
        """
        card = self._index.by_id.get(card_id)
        if card is None:
            raise CardNotFoundError(str(card_id))
        return card

    def get_by_name(self, name: str) -> Card:
        """Return the first card whose name exactly matches *name* (case-insensitive).

        Raises:
            CardNotFoundError: if no exact match is found.
        """
        cards = self._index.by_name_lower.get(name.lower())
        if not cards:
            raise CardNotFoundError(name)
        return cards[0]

    def find_by_name(self, name: str) -> list[Card]:
        """Return all cards sharing *name* (exact, case-insensitive).

        Returns an empty list when nothing matches.
        """
        return list(self._index.by_name_lower.get(name.lower(), []))

    # ------------------------------------------------------------------
    # Fuzzy / text search
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        *,
        threshold: int = 70,
        limit: int = 10,
    ) -> list[Card]:
        """Fuzzy search by card name.

        Args:
            query:     The search string (typos tolerated).
            threshold: Minimum similarity score (0–100).
            limit:     Maximum results.

        Returns:
            Ordered list of matching cards (best match first).
        """
        return search_by_name(
            self._index,
            query,
            threshold=threshold,
            limit=limit,
        )

    def search_contains(self, substring: str, *, limit: int = 50) -> list[Card]:
        """Return cards whose name contains *substring* (case-insensitive)."""
        return search_contains(self._index, substring, limit=limit)

    def search_effect(self, keyword: str, *, limit: int = 50) -> list[Card]:
        """Return cards whose effect text contains *keyword*."""
        return search_effect_text(self._index, keyword, limit=limit)

    def find_similar_name(self, name: str, *, limit: int = 5) -> list[Card]:
        """Return the closest name matches for a potentially misspelled name."""
        return search_by_name(
            self._index,
            name,
            threshold=50,
            limit=limit,
            exact_first=False,
        )

    # ------------------------------------------------------------------
    # Typed filters
    # ------------------------------------------------------------------

    def by_type(self, pokemon_type: PokemonType) -> list[PokemonCard]:
        """All Pokémon of the given type."""
        return list(self._index.by_type.get(pokemon_type, []))

    def by_stage(self, stage: Stage) -> list[PokemonCard]:
        """All Pokémon at the given evolution stage."""
        return list(self._index.by_stage.get(stage, []))

    def by_expansion(self, expansion: ExpansionCode) -> list[Card]:
        """All cards from the given expansion set."""
        return list(self._index.by_expansion.get(expansion, []))

    def by_hp(
        self,
        min_hp: int | None = None,
        max_hp: int | None = None,
    ) -> list[PokemonCard]:
        """Pokémon whose HP falls within [min_hp, max_hp] (inclusive).

        Pass None for either bound to skip that check.
        """
        results: list[PokemonCard] = []
        for hp, pokemon in self._index.by_hp.items():
            if min_hp is not None and hp < min_hp:
                continue
            if max_hp is not None and hp > max_hp:
                continue
            results.extend(pokemon)
        results.sort(key=lambda c: c.hp)
        return results

    def by_trainer_type(self, trainer_type: TrainerType) -> list[TrainerCard]:
        """All trainer cards of the given sub-type."""
        return list(self._index.by_trainer_type.get(trainer_type, []))

    def by_energy_type(self, energy_type: EnergyType) -> list[EnergyCard]:
        """All energy cards of the given type (Basic or Special)."""
        return list(self._index.by_energy_type.get(energy_type, []))

    def by_category(self, category: CardCategory) -> list[Card]:
        """All cards with the given category tag (Ancient, Future, Tera, etc.)."""
        return [c for c in self._cards if c.category == category]

    def by_rule_box(self, rule_box: RuleBox) -> list[Card]:
        """All cards with the given rule box designation."""
        return [c for c in self._cards if c.rule_box == rule_box]

    def by_energy_cost(
        self,
        max_total: int | None = None,
        *,
        requires_type: PokemonType | None = None,
    ) -> list[PokemonCard]:
        """Pokémon attacks satisfying energy cost constraints.

        Args:
            max_total:     Maximum total energy symbols in the cost.
            requires_type: If given, at least one attack must require this type.

        Returns the Pokémon cards (not attacks) that match.
        """
        results: list[PokemonCard] = []
        for card in self._all_pokemon():
            for atk in card.attacks:
                cost = atk.cost
                if max_total is not None and cost.total_count > max_total:
                    continue
                if requires_type is not None:
                    type_token = requires_type.value
                    if type_token not in cost.tokens:
                        continue
                results.append(card)
                break  # card qualifies; don't add it twice
        return results

    # ------------------------------------------------------------------
    # Convenience groupings
    # ------------------------------------------------------------------

    def list_all(self) -> list[Card]:
        """Return all cards in ascending ID order."""
        return sorted(self._cards, key=lambda c: c.card_id)

    def list_pokemon(self) -> list[PokemonCard]:
        """Return all Pokémon cards."""
        return self._all_pokemon()

    def list_trainers(self) -> list[TrainerCard]:
        """Return all Trainer cards."""
        return [c for c in self._cards if isinstance(c, TrainerCard)]

    def list_energies(self) -> list[EnergyCard]:
        """Return all Energy cards."""
        return [c for c in self._cards if isinstance(c, EnergyCard)]

    def list_ex_pokemon(self) -> list[PokemonCard]:
        """Return all Pokémon ex cards."""
        return [c for c in self._all_pokemon() if c.is_ex]

    def list_with_ability(self) -> list[PokemonCard]:
        """Return all Pokémon that have an Ability."""
        return [c for c in self._all_pokemon() if c.ability is not None]

    def evolves_from(self, pokemon_name: str) -> list[PokemonCard]:
        """Return all Pokémon that evolve from *pokemon_name*."""
        name_lower = pokemon_name.lower()
        return [
            c
            for c in self._all_pokemon()
            if c.previous_stage is not None
            and c.previous_stage.lower() == name_lower
        ]

    # ------------------------------------------------------------------
    # Generic filter
    # ------------------------------------------------------------------

    def filter(self, predicate: Callable[[Card], bool]) -> list[Card]:
        """Return all cards for which *predicate* returns True."""
        return [c for c in self._cards if predicate(c)]

    # ------------------------------------------------------------------
    # Stats / introspection
    # ------------------------------------------------------------------

    @property
    def total_cards(self) -> int:
        return len(self._cards)

    @property
    def parse_errors(self) -> list:
        return list(self._parse_errors)

    @property
    def validation_report(self) -> ValidationReport | None:
        return self._validation

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _all_pokemon(self) -> list[PokemonCard]:
        return [c for c in self._cards if isinstance(c, PokemonCard)]


# ---------------------------------------------------------------------------
# Convenience factory
# ---------------------------------------------------------------------------


def load_repository(
    csv_path: str | Path | None = None,
    *,
    run_validation: bool = True,
) -> CardRepository:
    """Load and return a CardRepository from the standard CSV path.

    Args:
        csv_path:       Path to EN_Card_Data.csv.  If None, defaults to
                        the project root (auto-detected from this file's
                        location).
        run_validation: Whether to run the post-parse validator.

    Returns:
        A fully initialised CardRepository.
    """
    if csv_path is None:
        # Walk up from this file to find the project root
        here = Path(__file__).resolve()
        project_root = here.parents[2]  # src/cards/ → src/ → project root
        csv_path = project_root / "EN_Card_Data.csv"

    csv_path = Path(csv_path)
    logger.info("Loading card repository from {}", csv_path)
    return CardRepository.from_csv(csv_path, run_validation=run_validation)
