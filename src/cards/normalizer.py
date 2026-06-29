"""
Field normalisation for raw CSV values.

Every function in this module is pure (no side effects, no I/O).
They accept a raw string and return a normalised domain object or raise
NormalizationError with a descriptive message.

Observations from the CSV:
  - Energy symbols: {G} {R} {W} {L} {P} {F} {D} {M} {C}
  - Colorless energy in cost is written as ● (bullet), not {C}
  - Dragon type is written as 竜 (Japanese character)
  - "n/a" means "not applicable" (distinct from empty string)
  - Empty string means "unknown / not provided"
  - Abilities are flagged by "[Ability]" prefix in Move Name
  - Tera rule-boxes are flagged by "[Tera]" in Move Name
  - Damage may be "120×" (variable), "-120" (reduction), or "n/a"
"""

from __future__ import annotations

import re

from loguru import logger

from src.cards.enums import (
    CardCategory,
    DamageModifier,
    EnergyType,
    ExpansionCode,
    PokemonType,
    RuleBox,
    Stage,
    TrainerType,
)
from src.cards.exceptions import NormalizationError
from src.cards.models import (
    DamageValue,
    EnergyCostModel,
    ResistanceModel,
    WeaknessModel,
)

# ---- Constants -------------------------------------------------------------

NA = "n/a"
BULLET = "●"
COLORLESS_TOKEN = "{C}"

# Maps CSV stage strings to Stage enum
_STAGE_MAP: dict[str, Stage] = {
    "Basic Pokémon": Stage.BASIC,
    "Stage 1 Pokémon": Stage.STAGE_1,
    "Stage 2 Pokémon": Stage.STAGE_2,
}

# Maps CSV rule strings to RuleBox enum
_RULE_MAP: dict[str, RuleBox] = {
    NA: RuleBox.NONE,
    "Pokémon ex": RuleBox.POKEMON_EX,
    "Mega Pokémon ex": RuleBox.MEGA_POKEMON_EX,
    "ACE SPEC": RuleBox.ACE_SPEC,
}

# Maps raw type symbol strings to PokemonType
_TYPE_SYMBOL_MAP: dict[str, PokemonType] = {
    "{G}": PokemonType.GRASS,
    "{R}": PokemonType.FIRE,
    "{W}": PokemonType.WATER,
    "{L}": PokemonType.LIGHTNING,
    "{P}": PokemonType.PSYCHIC,
    "{F}": PokemonType.FIGHTING,
    "{D}": PokemonType.DARK,
    "{M}": PokemonType.METAL,
    "{C}": PokemonType.COLORLESS,
    "竜": PokemonType.DRAGON,
    "{A}": PokemonType.ANY,
    "{Team Rocket}": PokemonType.TEAM_ROCKET,
    # Multi-token special energy types — provide COLORLESS / ANY sentinel
    "{A}{A}": PokemonType.ANY,
    "{C}{C}{C}": PokemonType.COLORLESS,
    "{Team Rocket}{Team Rocket}": PokemonType.TEAM_ROCKET,
}

# Regex to extract all {X} tokens from a cost string
_ENERGY_TOKEN_RE = re.compile(r"\{[^}]+\}")


# ---- Primitive helpers -----------------------------------------------------


def _clean(value: str) -> str:
    """Strip whitespace and normalise unicode spaces."""
    return value.strip().replace("　", " ").replace("\xa0", " ")


def _is_na(value: str) -> bool:
    return _clean(value).lower() == "n/a"


def _is_empty(value: str) -> bool:
    return not _clean(value)


# ---- Stage normalisation ---------------------------------------------------


def normalize_stage(raw: str) -> Stage:
    """Convert a CSV stage string to a Stage enum."""
    cleaned = _clean(raw)
    stage = _STAGE_MAP.get(cleaned)
    if stage is None:
        raise NormalizationError("stage", raw, f"Unknown stage: {cleaned!r}")
    return stage


# ---- Trainer type ----------------------------------------------------------


def normalize_trainer_type(raw: str) -> TrainerType:
    """Convert a CSV stage/type string to a TrainerType enum."""
    cleaned = _clean(raw)
    try:
        return TrainerType(cleaned)
    except ValueError:
        raise NormalizationError("trainer_type", raw, f"Unknown trainer type: {cleaned!r}")


# ---- Energy type -----------------------------------------------------------


def normalize_energy_supertype(raw: str) -> EnergyType:
    """Convert 'Basic Energy' / 'Special Energy' to EnergyType."""
    cleaned = _clean(raw)
    try:
        return EnergyType(cleaned)
    except ValueError:
        raise NormalizationError("energy_type", raw, f"Unknown energy type: {cleaned!r}")


# ---- Rule box --------------------------------------------------------------


def normalize_rule_box(raw: str) -> RuleBox:
    """Convert a CSV rule string to a RuleBox enum."""
    cleaned = _clean(raw)
    rule = _RULE_MAP.get(cleaned)
    if rule is None:
        logger.warning("Unknown rule box value {!r}; defaulting to NONE", raw)
        return RuleBox.NONE
    return rule


# ---- Card category ---------------------------------------------------------


def normalize_category(raw: str) -> CardCategory:
    """Convert a CSV category string to a CardCategory enum."""
    cleaned = _clean(raw)
    if _is_na(cleaned) or _is_empty(cleaned):
        return CardCategory.NONE
    try:
        return CardCategory(cleaned)
    except ValueError:
        logger.warning("Unknown category {!r}; storing as UNKNOWN", raw)
        return CardCategory.UNKNOWN


# ---- Expansion code --------------------------------------------------------


def normalize_expansion(raw: str) -> ExpansionCode:
    """Convert a CSV expansion code to an ExpansionCode enum."""
    cleaned = _clean(raw)
    try:
        return ExpansionCode(cleaned)
    except ValueError:
        logger.warning("Unknown expansion code {!r}; storing as UNKNOWN", raw)
        return ExpansionCode.UNKNOWN


# ---- HP -------------------------------------------------------------------


def normalize_hp(raw: str) -> int:
    """Parse an HP string into an integer.

    Raises NormalizationError if the value is not a positive integer.
    'n/a' is not valid for Pokémon cards — the caller must guard against
    passing non-Pokémon rows.
    """
    cleaned = _clean(raw)
    if not cleaned.isdigit():
        raise NormalizationError("hp", raw, f"Expected a positive integer, got {cleaned!r}")
    hp = int(cleaned)
    if hp <= 0:
        raise NormalizationError("hp", raw, "HP must be > 0")
    return hp


# ---- Pokémon type ----------------------------------------------------------


def normalize_pokemon_type(raw: str) -> PokemonType:
    """Convert a type symbol string to a PokemonType enum."""
    cleaned = _clean(raw)
    ptype = _TYPE_SYMBOL_MAP.get(cleaned)
    if ptype is None:
        logger.warning("Unknown Pokémon type symbol {!r}; storing as UNKNOWN", raw)
        return PokemonType.UNKNOWN
    return ptype


def normalize_provides(raw: str) -> tuple[PokemonType, ...]:
    """Parse the energy type(s) a Special Energy card provides.

    For basic energies the Type column contains a single symbol like {G}.
    For special energies it may be {A}, {A}{A}, {C}{C}{C}, etc.
    """
    cleaned = _clean(raw)
    if _is_na(cleaned) or _is_empty(cleaned):
        return (PokemonType.UNKNOWN,)
    tokens = _ENERGY_TOKEN_RE.findall(cleaned)
    if tokens:
        types: list[PokemonType] = []
        for tok in tokens:
            mapped = _TYPE_SYMBOL_MAP.get(tok, PokemonType.UNKNOWN)
            if mapped not in types:
                types.append(mapped)
        return tuple(types)
    # Might be a bare symbol like 竜
    ptype = _TYPE_SYMBOL_MAP.get(cleaned)
    if ptype is not None:
        return (ptype,)
    logger.warning("Cannot parse energy provision from {!r}", raw)
    return (PokemonType.UNKNOWN,)


# ---- Weakness / Resistance -------------------------------------------------


def normalize_weakness(raw: str) -> WeaknessModel | None:
    """Parse weakness field.  Returns None when the card has no weakness."""
    cleaned = _clean(raw)
    if _is_na(cleaned) or _is_empty(cleaned):
        return None
    ptype = _TYPE_SYMBOL_MAP.get(cleaned)
    if ptype is None:
        logger.warning("Unknown weakness type {!r}; ignoring", raw)
        return None
    return WeaknessModel(energy_type=ptype, multiplier=2)


def normalize_resistance(raw: str) -> ResistanceModel | None:
    """Parse resistance field.  Returns None when the card has no resistance."""
    cleaned = _clean(raw)
    if _is_na(cleaned) or _is_empty(cleaned):
        return None
    ptype = _TYPE_SYMBOL_MAP.get(cleaned)
    if ptype is None:
        logger.warning("Unknown resistance type {!r}; ignoring", raw)
        return None
    return ResistanceModel(energy_type=ptype, reduction=30)


# ---- Retreat cost ----------------------------------------------------------


def normalize_retreat(raw: str) -> int:
    """Parse retreat cost into an integer number of Energy cards required."""
    cleaned = _clean(raw)
    if _is_na(cleaned) or _is_empty(cleaned):
        return 0
    if cleaned.isdigit():
        return int(cleaned)
    raise NormalizationError("retreat", raw, f"Expected a digit or n/a, got {cleaned!r}")


# ---- Energy cost -----------------------------------------------------------


def normalize_energy_cost(raw: str) -> EnergyCostModel:
    """Parse an attack's cost string into an EnergyCostModel.

    Cost strings use energy symbols ({G}, {R}, …) and ● for colorless.
    'No cost' means the attack is free.
    'n/a' appears on Ability rows and Trainer effect rows.
    """
    cleaned = _clean(raw)

    if cleaned == "No cost":
        return EnergyCostModel.free()

    if _is_na(cleaned) or _is_empty(cleaned):
        return EnergyCostModel(tokens=(), total_count=0)

    tokens: list[str] = []

    # Extract typed energy tokens first
    cursor = 0
    pos = 0
    while pos < len(cleaned):
        if cleaned[pos] == "{":
            end = cleaned.find("}", pos)
            if end == -1:
                break
            tokens.append(cleaned[pos : end + 1])
            pos = end + 1
        elif cleaned[pos] == BULLET:
            tokens.append(COLORLESS_TOKEN)
            pos += 1
        else:
            pos += 1

    return EnergyCostModel(tokens=tuple(tokens), total_count=len(tokens))


# ---- Damage ----------------------------------------------------------------


_DAMAGE_VARIABLE_RE = re.compile(r"^(-?\d+)×$")
_DAMAGE_EXACT_RE = re.compile(r"^(-?\d+)$")


def normalize_damage(raw: str) -> DamageValue:
    """Parse a damage string into a DamageValue.

    Possible formats:
      "n/a"   → no damage (effect-only)
      "120"   → exact 120
      "120×"  → variable (base 120, scales with condition)
      "-120"  → negative (damage reduction mechanic in effect text)
    """
    cleaned = _clean(raw)

    if _is_na(cleaned) or _is_empty(cleaned):
        return DamageValue(base=0, modifier=DamageModifier.NONE, raw=raw)

    # Variable: e.g. "120×"
    m = _DAMAGE_VARIABLE_RE.match(cleaned)
    if m:
        return DamageValue(
            base=int(m.group(1)),
            modifier=DamageModifier.VARIABLE,
            raw=raw,
        )

    # Exact (possibly negative): e.g. "120" or "-120"
    m = _DAMAGE_EXACT_RE.match(cleaned)
    if m:
        val = int(m.group(1))
        modifier = DamageModifier.NEGATIVE if val < 0 else DamageModifier.EXACT
        return DamageValue(base=val, modifier=modifier, raw=raw)

    logger.warning("Unrecognised damage value {!r}; treating as n/a", raw)
    return DamageValue(base=0, modifier=DamageModifier.NONE, raw=raw)


# ---- Move Name helpers -----------------------------------------------------


def is_ability_row(move_name: str) -> bool:
    """Return True when the Move Name identifies an Ability."""
    return _clean(move_name).startswith("[Ability]")


def is_tera_row(move_name: str) -> bool:
    """Return True when the Move Name identifies a Tera passive."""
    return _clean(move_name).strip() == "[Tera]"


def extract_ability_name(move_name: str) -> str:
    """Strip the [Ability] prefix and return the bare ability name."""
    cleaned = _clean(move_name)
    return cleaned.removeprefix("[Ability]").strip()


# ---- Text sanitisation -----------------------------------------------------


def normalize_text(raw: str) -> str:
    """Normalise free-text fields: strip, collapse internal whitespace."""
    cleaned = _clean(raw)
    if _is_na(cleaned):
        return ""
    # Collapse runs of whitespace
    return " ".join(cleaned.split())


def normalize_name(raw: str) -> str:
    """Normalise a card or move name."""
    return normalize_text(raw)


def normalize_previous_stage(raw: str) -> str | None:
    """Return None when there is no previous stage, else the Pokémon name."""
    cleaned = _clean(raw)
    if _is_na(cleaned) or _is_empty(cleaned):
        return None
    return normalize_name(cleaned)


def normalize_collection_number(raw: str) -> str:
    """Return the collection number as a stripped string."""
    return _clean(raw)
