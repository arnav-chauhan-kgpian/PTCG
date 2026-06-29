"""
Fuzzy and exact search over the card database.

Uses rapidfuzz for typo-tolerant name matching.
All search functions accept the CardIndex built by cache.build_index()
so they impose no I/O or initialisation cost of their own.

Examples:
    search_by_name(idx, "Pikacu")     → [Pikachu, …]
    search_by_name(idx, "Charzard")   → [Charizard, …]
    search_by_name(idx, "Charizard")  → [Charizard, …] (exact hit)
"""

from __future__ import annotations

from rapidfuzz import fuzz, process

from src.cards.cache import CardIndex
from src.cards.models import Card

# Minimum similarity score (0-100) for a fuzzy match to be included
_DEFAULT_THRESHOLD = 70
# Maximum number of candidates returned by a fuzzy search
_DEFAULT_LIMIT = 10


def search_by_name(
    index: CardIndex,
    query: str,
    *,
    threshold: int = _DEFAULT_THRESHOLD,
    limit: int = _DEFAULT_LIMIT,
    exact_first: bool = True,
) -> list[Card]:
    """Return cards whose name matches *query* (fuzzy).

    Args:
        index:        The CardIndex to search.
        query:        The search string (may contain typos).
        threshold:    Minimum rapidfuzz score (0–100) to include a result.
        limit:        Maximum results to return.
        exact_first:  If a case-insensitive exact match exists, return it
                      at the top and skip the fuzzy pass.

    Returns:
        A list of Card objects ordered by match quality (best first).
    """
    q = query.strip()
    if not q:
        return []

    # Fast exact path — avoids calling rapidfuzz for common lookups
    if exact_first:
        exact = index.by_name_lower.get(q.lower())
        if exact:
            return list(exact)

    # Fuzzy matching against the full name corpus
    matches = process.extract(
        q,
        index.all_names,
        scorer=fuzz.WRatio,
        limit=limit,
        score_cutoff=threshold,
    )

    # Deduplicate while preserving order (rapidfuzz may return the same
    # name multiple times if reprints exist)
    seen: set[str] = set()
    results: list[Card] = []
    for name, _score, _idx in matches:
        if name in seen:
            continue
        seen.add(name)
        for card in index.by_name.get(name, []):
            results.append(card)
        if len(results) >= limit:
            break

    return results


def search_contains(
    index: CardIndex,
    substring: str,
    *,
    limit: int = 50,
) -> list[Card]:
    """Return cards whose name contains *substring* (case-insensitive)."""
    sub = substring.lower()
    results: list[Card] = []
    for name_lower, cards in index.by_name_lower.items():
        if sub in name_lower:
            results.extend(cards)
        if len(results) >= limit:
            break
    return results


def search_effect_text(
    index: CardIndex,
    keyword: str,
    *,
    limit: int = 50,
) -> list[Card]:
    """Return cards whose effect text contains *keyword* (case-insensitive).

    This is a linear scan — suitable for offline queries, not inner-loop use.
    """
    kw = keyword.lower()
    results: list[Card] = []
    for card in index.by_id.values():
        effect = _get_effect_text(card).lower()
        if kw in effect:
            results.append(card)
            if len(results) >= limit:
                break
    return results


def _get_effect_text(card: Card) -> str:
    """Extract all searchable text from a card."""
    from src.cards.models import EnergyCard, PokemonCard, TrainerCard

    parts: list[str] = [card.name]
    if isinstance(card, PokemonCard):
        if card.ability:
            parts.append(card.ability.name)
            parts.append(card.ability.effect)
        if card.tera_ability:
            parts.append(card.tera_ability.effect)
        for atk in card.attacks:
            parts.append(atk.name)
            parts.append(atk.effect)
    elif isinstance(card, TrainerCard):
        parts.append(card.effect)
        if card.embedded_ability:
            parts.append(card.embedded_ability.effect)
        if card.embedded_attack:
            parts.append(card.embedded_attack.effect)
    elif isinstance(card, EnergyCard):
        parts.append(card.effect)
    return " ".join(parts)
