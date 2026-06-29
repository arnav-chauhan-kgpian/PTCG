"""
Type aliases used throughout the card knowledge layer.

Centralising these here means downstream modules never import
from typing directly just for a primitive alias.
"""

from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
    from src.cards.models import EnergyCard, PokemonCard, TrainerCard

# A cost string is a sequence of energy-type tokens e.g. ["{G}", "{C}", "{C}"]
EnergyCostToken = str
EnergyCost = list[EnergyCostToken]

# Raw damage from the CSV before parsing
RawDamage = str

# A card's numeric identifier
CardId = int

# Convenience union over the three concrete card types
AnyCard = Union["PokemonCard", "TrainerCard", "EnergyCard"]
