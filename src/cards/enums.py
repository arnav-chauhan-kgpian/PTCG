"""
All enumerations for the Pokémon TCG card domain.

Symbol mapping from the CSV:
  {G} Grass   {R} Fire    {W} Water   {L} Lightning
  {P} Psychic {F} Fighting {D} Dark   {M} Metal
  {C} Colorless (also represented by ● in cost strings)
  {A} Any     竜  Dragon   (Special energies and Tera types)
"""

from enum import Enum


class PokemonType(str, Enum):
    """Pokémon elemental types.  Values match the CSV symbol for easy lookup."""

    GRASS = "{G}"
    FIRE = "{R}"
    WATER = "{W}"
    LIGHTNING = "{L}"
    PSYCHIC = "{P}"
    FIGHTING = "{F}"
    DARK = "{D}"
    METAL = "{M}"
    COLORLESS = "{C}"
    DRAGON = "竜"
    # Special-energy "any type" marker
    ANY = "{A}"
    # Team Rocket special energy marker (appears in CSV as-is)
    TEAM_ROCKET = "{Team Rocket}"
    # Sentinel for truly unknown values
    UNKNOWN = "unknown"


class EnergyType(str, Enum):
    """Energy card sub-classifications."""

    BASIC = "Basic Energy"
    SPECIAL = "Special Energy"


class TrainerType(str, Enum):
    """Trainer card sub-classifications."""

    ITEM = "Item"
    SUPPORTER = "Supporter"
    STADIUM = "Stadium"
    POKEMON_TOOL = "Pokémon Tool"


class Stage(str, Enum):
    """Evolution stage for Pokémon cards."""

    BASIC = "Basic Pokémon"
    STAGE_1 = "Stage 1 Pokémon"
    STAGE_2 = "Stage 2 Pokémon"


class RuleBox(str, Enum):
    """Special rule designators that appear on cards."""

    POKEMON_EX = "Pokémon ex"
    MEGA_POKEMON_EX = "Mega Pokémon ex"
    ACE_SPEC = "ACE SPEC"
    NONE = "n/a"


class CardCategory(str, Enum):
    """Thematic sub-category attached to certain cards."""

    NONE = "n/a"
    ANCIENT = "Ancient"
    FUTURE = "Future"
    FOSSIL = "Fossil"
    TECHNICAL_MACHINE = "Technical Machine"

    TERA_GRASS = "Tera(Grass)"
    TERA_FIRE = "Tera(Fire)"
    TERA_WATER = "Tera(Water)"
    TERA_LIGHTNING = "Tera(Lightning)"
    TERA_PSYCHIC = "Tera(Psychic)"
    TERA_FIGHTING = "Tera(Fighting)"
    TERA_DARK = "Tera(Dark)"
    TERA_METAL = "Tera(Metal)"
    TERA_DRAGON = "Tera(Dragon)"
    TERA_DARKNESS = "Tera(Darkness)"
    TERA_STELLAR = "Tera(Stellar)"

    TRAINER_ARVEN = "Trainer's Pokémon（Arven）"
    TRAINER_CYNTHIA = "Trainer's Pokémon（Cynthia）"
    TRAINER_ERIKA = "Trainer's Pokémon（Erika）"
    TRAINER_ETHAN = "Trainer's Pokémon（Ethan）"
    TRAINER_HOP = "Trainer's Pokémon（Hop）"
    TRAINER_IONO = "Trainer's Pokémon（Iono）"
    TRAINER_LARRY = "Trainer's Pokémon（Larry）"
    TRAINER_LILLIE = "Trainer's Pokémon（Lillie）"
    TRAINER_MARNIE = "Trainer's Pokémon（Marnie）"
    TRAINER_MISTY = "Trainer's Pokémon（Misty）"
    TRAINER_N = "Trainer's Pokémon（N）"
    TRAINER_STEVEN = "Trainer's Pokémon（Steven）"
    TRAINER_TEAM_ROCKET = "Trainer's Pokémon（Team Rocket）"

    UNKNOWN = "unknown"


class ExpansionCode(str, Enum):
    """Known expansion set codes from the CSV."""

    SVE = "SVE"
    TWM = "TWM"
    TEF = "TEF"
    MEG = "MEG"
    BLK = "BLK"
    WHT = "WHT"
    DRI = "DRI"
    ASC = "ASC"
    SSP = "SSP"
    JTG = "JTG"
    SFA = "SFA"
    SCR = "SCR"
    POR = "POR"
    PFL = "PFL"
    PRE = "PRE"
    PAL = "PAL"
    SVI = "SVI"
    SVP = "SVP"
    PROMO = "PROMO"
    UNKNOWN = ""


class DamageModifier(str, Enum):
    """Damage value qualifiers."""

    EXACT = "exact"        # e.g. "120"
    VARIABLE = "variable"  # e.g. "120×"
    NONE = "n/a"           # no damage (effect-only attack)
    NEGATIVE = "negative"  # e.g. "-120" (damage reduction in effect text)


class StatusCondition(str, Enum):
    """Pokémon status conditions (used in effect text parsing)."""

    ASLEEP = "Asleep"
    CONFUSED = "Confused"
    PARALYZED = "Paralyzed"
    POISONED = "Poisoned"
    BURNED = "Burned"


class CardSuperType(str, Enum):
    """Top-level card classification."""

    POKEMON = "pokemon"
    TRAINER = "trainer"
    ENERGY = "energy"
