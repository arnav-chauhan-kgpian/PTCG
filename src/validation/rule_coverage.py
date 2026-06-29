"""
RuleCoverageReport — measure how much of the card set the simulator
fully executes.

Used by the dashboard and the final report.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.cards.repository import CardRepository


_SUPPORTED_EFFECTS: set[str] = {
    "DrawCards", "HealEffect", "DamageCounters", "SelfDamage", "BenchDamage",
    "CompositeEffect", "ConditionalEffect", "DiscardEffect", "AttachEnergy",
    "MoveEnergy", "StatusConditionEffect", "SwitchActive", "ForceSwitch",
    "ShuffleEffect", "MillEffect", "SearchDeck", "SearchDiscard",
    "ReturnToHand", "DamageModifier", "VariableDamage", "PreventDamage",
    "AbilitySuppression", "PassiveEffect", "RetreatCostEffect",
    "ToolInteraction", "StadiumInteraction", "KnockOut", "CoinFlip",
}


@dataclass
class RuleCoverageReport:
    trainers_total: int = 0
    trainers_supported: int = 0
    attacks_total: int = 0
    attacks_supported: int = 0
    abilities_total: int = 0
    abilities_supported: int = 0
    named_trainer_handlers: int = 0
    named_ability_handlers: int = 0
    energy_card_total: int = 0
    pokemon_total: int = 0
    unsupported_effect_classes_observed: list[str] = field(default_factory=list)

    @property
    def trainer_coverage(self) -> float:
        return self.trainers_supported / max(1, self.trainers_total)

    @property
    def attack_coverage(self) -> float:
        return self.attacks_supported / max(1, self.attacks_total)

    @property
    def ability_coverage(self) -> float:
        return self.abilities_supported / max(1, self.abilities_total)

    def to_dict(self) -> dict:
        return {
            "trainers_total": self.trainers_total,
            "trainers_supported": self.trainers_supported,
            "trainer_coverage": round(self.trainer_coverage, 4),
            "attacks_total": self.attacks_total,
            "attacks_supported": self.attacks_supported,
            "attack_coverage": round(self.attack_coverage, 4),
            "abilities_total": self.abilities_total,
            "abilities_supported": self.abilities_supported,
            "ability_coverage": round(self.ability_coverage, 4),
            "named_trainer_handlers": self.named_trainer_handlers,
            "named_ability_handlers": self.named_ability_handlers,
            "pokemon_total": self.pokemon_total,
            "energy_card_total": self.energy_card_total,
            "unsupported_effect_classes_observed":
                list(self.unsupported_effect_classes_observed),
        }


def measure_rule_coverage(
    repository: CardRepository,
) -> RuleCoverageReport:
    """Cross-reference the card set against supported effect classes."""
    from src.cards.effects import parse_effect
    from src.cards.models import EnergyCard, PokemonCard, TrainerCard
    from src.simulator import named_ability_handlers, named_trainer_handlers

    report = RuleCoverageReport()
    cards = repository.list_all()
    trainers = [c for c in cards if isinstance(c, TrainerCard)]
    pokemon = [c for c in cards if isinstance(c, PokemonCard)]
    energies = [c for c in cards if isinstance(c, EnergyCard)]
    abilities = [p for p in pokemon if getattr(p, "ability", None) is not None]

    report.trainers_total = len(trainers)
    report.pokemon_total = len(pokemon)
    report.energy_card_total = len(energies)
    report.abilities_total = len(abilities)

    named_t = set(named_trainer_handlers().keys())
    named_a = set(named_ability_handlers().keys())
    report.named_trainer_handlers = len(named_t)
    report.named_ability_handlers = len(named_a)

    def _root_classes(eff):
        cls = type(eff).__name__
        if cls == "CompositeEffect":
            names: set[str] = set()
            for child in getattr(eff, "effects", ()) or ():
                names |= _root_classes(child)
            return names
        return {cls}

    for t in trainers:
        if t.name in named_t:
            report.trainers_supported += 1
            continue
        text = (t.effect or "").strip()
        if not text:
            continue
        try:
            eff = parse_effect(text)
            if _root_classes(eff) <= _SUPPORTED_EFFECTS:
                report.trainers_supported += 1
        except Exception:
            pass

    for p in pokemon:
        for a in p.attacks:
            report.attacks_total += 1
            text = (a.effect or "").strip()
            if not text:
                report.attacks_supported += 1
                continue
            try:
                eff = parse_effect(text)
                if _root_classes(eff) <= _SUPPORTED_EFFECTS:
                    report.attacks_supported += 1
            except Exception:
                pass

    for p in abilities:
        if p.name in named_a:
            report.abilities_supported += 1
            continue
        text = (p.ability.effect or "").strip()
        if not text:
            continue
        try:
            eff = parse_effect(text)
            if _root_classes(eff) <= _SUPPORTED_EFFECTS:
                report.abilities_supported += 1
        except Exception:
            pass

    return report
