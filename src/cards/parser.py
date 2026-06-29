"""
CSV parser for EN_Card_Data.csv.

The CSV is NOT normalised:
  - Pokémon with multiple attacks appear as multiple rows sharing the same Card ID.
  - Pokémon with abilities have an extra row where Move Name starts with [Ability].
  - Tera Pokémon ex have an extra [Tera] row describing the Tera passive.
  - Fossil Items and Technical-Machine Tools can have embedded ability/attack rows.
  - Trainer and Energy cards appear once each.

Algorithm:
  1. Stream all rows into a dict keyed by Card ID, collecting a list of raw rows.
  2. For each Card ID, inspect the first row to determine card super-type
     (Pokémon / Trainer / Energy).
  3. Delegate to a type-specific builder that collapses the row group into one
     model instance.

Returns a ParseResult containing all successfully parsed cards plus a list of
warnings/errors for cards that could not be parsed.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

from loguru import logger

from src.cards.enums import CardSuperType, EnergyType, Stage, TrainerType
from src.cards.exceptions import ParseError
from src.cards.models import (
    Ability,
    Attack,
    Card,
    EnergyCard,
    PokemonCard,
    TeraAbility,
    TrainerCard,
)
from src.cards.normalizer import (
    extract_ability_name,
    is_ability_row,
    is_tera_row,
    normalize_category,
    normalize_collection_number,
    normalize_damage,
    normalize_energy_cost,
    normalize_energy_supertype,
    normalize_expansion,
    normalize_hp,
    normalize_name,
    normalize_pokemon_type,
    normalize_previous_stage,
    normalize_provides,
    normalize_resistance,
    normalize_retreat,
    normalize_rule_box,
    normalize_stage,
    normalize_text,
    normalize_trainer_type,
    normalize_weakness,
)

# Column name constants (exactly as they appear in the CSV header)
_COL_ID = "Card ID"
_COL_NAME = "Card Name"
_COL_EXP = "Expansion"
_COL_COLNO = "Collection No."
_COL_STAGE = "Stage (Pokémon)/Type (Energy and Trainer)"
_COL_RULE = "Rule"
_COL_CATEGORY = "Category"
_COL_PREV = "Previous stage"
_COL_HP = "HP"
_COL_TYPE = "Type"
_COL_WEAK = "Weakness"
_COL_RES = "Resistance (Type)"
_COL_RETREAT = "Retreat"
_COL_MOVE = "Move Name"
_COL_COST = "Cost"
_COL_DMG = "Damage"
_COL_EFF = "Effect Explanation"

# Stage strings that identify Pokémon rows
_POKEMON_STAGES = frozenset(s.value for s in Stage)

# Trainer type strings
_TRAINER_TYPES = frozenset(t.value for t in TrainerType)

# Energy type strings
_ENERGY_TYPES = frozenset(e.value for e in EnergyType)

RawRow = dict[str, str]


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------


@dataclass
class ParseResult:
    """Container for a completed parse pass."""

    cards: list[Card] = field(default_factory=list)
    errors: list[ParseError] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def pokemon(self) -> list[PokemonCard]:
        return [c for c in self.cards if isinstance(c, PokemonCard)]

    @property
    def trainers(self) -> list[TrainerCard]:
        return [c for c in self.cards if isinstance(c, TrainerCard)]

    @property
    def energies(self) -> list[EnergyCard]:
        return [c for c in self.cards if isinstance(c, EnergyCard)]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _supertype(stage_value: str) -> CardSuperType:
    if stage_value in _POKEMON_STAGES:
        return CardSuperType.POKEMON
    if stage_value in _TRAINER_TYPES:
        return CardSuperType.TRAINER
    if stage_value in _ENERGY_TYPES:
        return CardSuperType.ENERGY
    return CardSuperType.POKEMON  # Unknown rows treated as Pokémon (edge-case catch)


def _build_attack(row: RawRow) -> Attack | None:
    """Build an Attack from a CSV row.  Returns None for ability/tera rows."""
    move_name = row[_COL_MOVE].strip()
    if not move_name or move_name == "n/a":
        return None
    if is_ability_row(move_name) or is_tera_row(move_name):
        return None

    return Attack(
        name=normalize_name(move_name),
        cost=normalize_energy_cost(row[_COL_COST]),
        damage=normalize_damage(row[_COL_DMG]),
        effect=normalize_text(row[_COL_EFF]),
    )


def _build_ability(row: RawRow) -> Ability | None:
    """Build an Ability from a CSV row.  Returns None for attack/tera rows."""
    move_name = row[_COL_MOVE].strip()
    if not is_ability_row(move_name):
        return None
    return Ability(
        name=extract_ability_name(move_name),
        effect=normalize_text(row[_COL_EFF]),
    )


def _build_tera(row: RawRow) -> TeraAbility | None:
    """Build a TeraAbility from a [Tera] row."""
    move_name = row[_COL_MOVE].strip()
    if not is_tera_row(move_name):
        return None
    return TeraAbility(effect=normalize_text(row[_COL_EFF]))


# ---------------------------------------------------------------------------
# Card-type builders
# ---------------------------------------------------------------------------


def _build_pokemon(card_id: int, rows: list[RawRow]) -> PokemonCard:
    """Merge all rows for a single Pokémon ID into one PokemonCard."""
    base = rows[0]

    attacks: list[Attack] = []
    ability: Ability | None = None
    tera: TeraAbility | None = None

    for row in rows:
        atk = _build_attack(row)
        if atk is not None:
            attacks.append(atk)
            continue

        abl = _build_ability(row)
        if abl is not None:
            if ability is not None:
                logger.warning(
                    "Card {} ({}) has multiple Ability rows; keeping first",
                    card_id,
                    base[_COL_NAME],
                )
            else:
                ability = abl
            continue

        tera_abl = _build_tera(row)
        if tera_abl is not None:
            tera = tera_abl
            continue

        # Row with empty Move Name for a Pokémon — skip silently
        if not row[_COL_MOVE].strip():
            logger.debug("Card {} has empty Move Name row; skipping", card_id)

    return PokemonCard(
        card_id=card_id,
        name=normalize_name(base[_COL_NAME]),
        expansion=normalize_expansion(base[_COL_EXP]),
        collection_number=normalize_collection_number(base[_COL_COLNO]),
        rule_box=normalize_rule_box(base[_COL_RULE]),
        category=normalize_category(base[_COL_CATEGORY]),
        stage=normalize_stage(base[_COL_STAGE]),
        previous_stage=normalize_previous_stage(base[_COL_PREV]),
        hp=normalize_hp(base[_COL_HP]),
        pokemon_type=normalize_pokemon_type(base[_COL_TYPE]),
        weakness=normalize_weakness(base[_COL_WEAK]),
        resistance=normalize_resistance(base[_COL_RES]),
        retreat_cost=normalize_retreat(base[_COL_RETREAT]),
        ability=ability,
        tera_ability=tera,
        attacks=tuple(attacks),
    )


def _build_trainer(card_id: int, rows: list[RawRow]) -> TrainerCard:
    """Build a TrainerCard from its row group.

    Most trainers have one row. Fossil Items and TM Tools have two:
      - Row 1: trainer effect text (Move Name is 'n/a' or empty)
      - Row 2: embedded Ability (Fossil) or embedded Attack (TM)
    """
    base = rows[0]
    trainer_type = normalize_trainer_type(base[_COL_STAGE])

    # Primary effect: use the row where Move Name is blank or 'n/a'
    primary_effect_row = next(
        (r for r in rows if not r[_COL_MOVE].strip() or r[_COL_MOVE].strip() == "n/a"),
        base,
    )
    primary_effect = normalize_text(primary_effect_row[_COL_EFF])

    embedded_ability: Ability | None = None
    embedded_attack: Attack | None = None

    for row in rows:
        abl = _build_ability(row)
        if abl is not None:
            embedded_ability = abl
            continue
        atk = _build_attack(row)
        if atk is not None:
            embedded_attack = atk

    return TrainerCard(
        card_id=card_id,
        name=normalize_name(base[_COL_NAME]),
        expansion=normalize_expansion(base[_COL_EXP]),
        collection_number=normalize_collection_number(base[_COL_COLNO]),
        rule_box=normalize_rule_box(base[_COL_RULE]),
        category=normalize_category(base[_COL_CATEGORY]),
        trainer_type=trainer_type,
        effect=primary_effect,
        embedded_ability=embedded_ability,
        embedded_attack=embedded_attack,
    )


def _build_energy(card_id: int, rows: list[RawRow]) -> EnergyCard:
    """Build an EnergyCard from its (always single) row."""
    base = rows[0]
    energy_type = normalize_energy_supertype(base[_COL_STAGE])
    return EnergyCard(
        card_id=card_id,
        name=normalize_name(base[_COL_NAME]),
        expansion=normalize_expansion(base[_COL_EXP]),
        collection_number=normalize_collection_number(base[_COL_COLNO]),
        rule_box=normalize_rule_box(base[_COL_RULE]),
        category=normalize_category(base[_COL_CATEGORY]),
        energy_type=energy_type,
        provides=normalize_provides(base[_COL_TYPE]),
        effect=normalize_text(base[_COL_EFF]),
    )


# ---------------------------------------------------------------------------
# Public parse function
# ---------------------------------------------------------------------------


def parse_csv(path: str | Path) -> ParseResult:
    """Parse the card CSV into a ParseResult.

    Steps:
    1. Stream all rows, group by Card ID.
    2. For each group, determine super-type from the first row's stage column.
    3. Delegate to the appropriate builder function.
    4. Collect errors without aborting the entire parse.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"CSV not found: {path}")

    result = ParseResult()

    # --- Group rows by card ID ------------------------------------------
    groups: dict[int, list[RawRow]] = {}
    row_num = 1  # 1-based (header is row 0)
    with path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        for raw_row in reader:
            row_num += 1
            raw_id = raw_row.get(_COL_ID, "").strip()
            if not raw_id.isdigit():
                result.warnings.append(
                    f"Row {row_num}: non-numeric Card ID {raw_id!r}; skipping"
                )
                continue
            cid = int(raw_id)
            groups.setdefault(cid, []).append(raw_row)

    logger.info("Grouped {} raw rows into {} unique card IDs", row_num - 1, len(groups))

    # --- Build one card per group ---------------------------------------
    for card_id, rows in sorted(groups.items()):
        try:
            stage_val = rows[0].get(_COL_STAGE, "").strip()
            supertype = _supertype(stage_val)

            if supertype == CardSuperType.POKEMON:
                card: Card = _build_pokemon(card_id, rows)
            elif supertype == CardSuperType.TRAINER:
                card = _build_trainer(card_id, rows)
            else:
                card = _build_energy(card_id, rows)

            result.cards.append(card)

        except Exception as exc:
            err = ParseError(
                row_number=0,
                card_id=str(card_id),
                message=str(exc),
            )
            result.errors.append(err)
            logger.warning("Failed to parse card {}: {}", card_id, exc)

    logger.info(
        "Parse complete: {} cards ({} pokemon, {} trainers, {} energies), {} errors",
        len(result.cards),
        len(result.pokemon),
        len(result.trainers),
        len(result.energies),
        len(result.errors),
    )
    return result
