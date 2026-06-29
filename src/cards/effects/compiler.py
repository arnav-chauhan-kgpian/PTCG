"""
compile_card — transform a parsed card into a CompiledCard with per-attack
and ability effects already resolved.

Usage::

    from src.cards.effects import compile_card
    from src.cards.repository import load_repository

    repo = load_repository(...)
    card = repo.by_id("1001")
    compiled = compile_card(card)
    # compiled.attack_effects["Hydro Pump"] → CompositeEffect(...)
    # compiled.ability_effect → PassiveEffect(...)
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.cards.effects.models import Effect, UnknownEffect
from src.cards.effects.parser import EffectParser
from src.cards.effects.registry import RuleRegistry
from src.cards.models import EnergyCard, PokemonCard, TrainerCard
from src.cards.types import AnyCard


@dataclass(frozen=True)
class CompiledCard:
    """Fully parsed representation of a single card.

    All string effect texts have been converted to typed Effect objects.

    Attributes:
        card_id:         Original card identifier.
        name:            Card name.
        attack_effects:  Mapping from attack name → parsed Effect.
        ability_effect:  Parsed Effect for the card's Ability/Tera
                         (None if the card has no ability).
        trainer_effect:  Parsed Effect for Trainer/Item/Stadium cards
                         (None for Pokémon and Energy).
        energy_effect:   Parsed Effect for Special Energy cards
                         (None for non-special energy).
    """
    card_id: str
    name: str
    attack_effects: dict[str, Effect] = field(default_factory=dict)
    ability_effect: Effect | None = None
    trainer_effect: Effect | None = None
    energy_effect: Effect | None = None

    def all_effects(self) -> list[Effect]:
        """Convenience — return every non-None Effect this card has."""
        out: list[Effect] = list(self.attack_effects.values())
        for e in (self.ability_effect, self.trainer_effect, self.energy_effect):
            if e is not None:
                out.append(e)
        return out


def compile_card(
    card: AnyCard,
    *,
    registry: RuleRegistry | None = None,
) -> CompiledCard:
    """Parse all text fields on *card* and return a CompiledCard.

    Args:
        card:     Any AnyCard subtype (PokemonCard, TrainerCard, EnergyCard).
        registry: Optional custom rule registry; defaults to the global one.

    Returns:
        CompiledCard with all effect strings resolved.
    """
    parser = EffectParser(registry)

    attack_effects: dict[str, Effect] = {}
    ability_effect: Effect | None = None
    trainer_effect: Effect | None = None
    energy_effect: Effect | None = None

    if isinstance(card, PokemonCard):
        for attack in card.attacks:
            raw = attack.effect or ""
            attack_effects[attack.name] = parser.parse(raw) if raw else UnknownEffect(text="", raw_text="")

        if card.ability is not None:
            raw_ab = card.ability.effect or ""
            ability_effect = parser.parse(raw_ab) if raw_ab else UnknownEffect(text="", raw_text="")

        if card.tera_ability is not None:
            raw_tera = card.tera_ability.effect or ""
            ability_effect = parser.parse(raw_tera) if raw_tera else ability_effect

    elif isinstance(card, TrainerCard):
        raw = card.effect or ""
        trainer_effect = parser.parse(raw) if raw else UnknownEffect(text="", raw_text="")

    elif isinstance(card, EnergyCard):
        raw = card.effect or ""
        if raw:
            energy_effect = parser.parse(raw)

    return CompiledCard(
        card_id=str(card.card_id),
        name=card.name,
        attack_effects=attack_effects,
        ability_effect=ability_effect,
        trainer_effect=trainer_effect,
        energy_effect=energy_effect,
    )
