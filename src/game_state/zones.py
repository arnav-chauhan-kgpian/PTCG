"""
Enumerations for all zone, status, and category types used in game state.
"""

from enum import Enum


class Zone(str, Enum):
    """Physical location of a card within the game."""
    DECK = "deck"
    HAND = "hand"
    ACTIVE = "active"
    BENCH = "bench"
    DISCARD = "discard"
    LOST_ZONE = "lost_zone"
    PRIZE = "prize"
    STADIUM = "stadium"
    ATTACHED = "attached"  # energy/tool attached to a Pokémon


class SpecialCondition(str, Enum):
    """Special conditions that can affect an Active Pokémon."""
    BURNED = "burned"
    POISONED = "poisoned"
    PARALYZED = "paralyzed"
    CONFUSED = "confused"
    ASLEEP = "asleep"


class GameStatus(str, Enum):
    """High-level game lifecycle status."""
    NOT_STARTED = "not_started"
    ONGOING = "ongoing"
    PLAYER_0_WIN = "player_0_win"
    PLAYER_1_WIN = "player_1_win"
    DRAW = "draw"


class CardCategory(str, Enum):
    """Broad functional category of a card."""
    POKEMON = "pokemon"
    TRAINER_ITEM = "trainer_item"
    TRAINER_SUPPORTER = "trainer_supporter"
    TRAINER_STADIUM = "trainer_stadium"
    TRAINER_TOOL = "trainer_tool"
    ENERGY_BASIC = "energy_basic"
    ENERGY_SPECIAL = "energy_special"


class EnergyTypeCode(str, Enum):
    """Single-letter energy type codes, aligned with PTCG notation."""
    FIRE = "R"
    WATER = "W"
    GRASS = "G"
    LIGHTNING = "L"
    PSYCHIC = "P"
    FIGHTING = "F"
    DARKNESS = "D"
    METAL = "M"
    DRAGON = "N"
    COLORLESS = "C"
    FAIRY = "Y"

    @classmethod
    def ordered(cls) -> tuple["EnergyTypeCode", ...]:
        return (
            cls.FIRE, cls.WATER, cls.GRASS, cls.LIGHTNING, cls.PSYCHIC,
            cls.FIGHTING, cls.DARKNESS, cls.METAL, cls.DRAGON,
            cls.COLORLESS, cls.FAIRY,
        )

    @classmethod
    def index(cls, code: "EnergyTypeCode") -> int:
        return cls.ordered().index(code)


class PokemonStage(str, Enum):
    """Evolution stage of a Pokémon card."""
    BASIC = "basic"
    STAGE_1 = "stage_1"
    STAGE_2 = "stage_2"
    V = "v"
    VMAX = "vmax"
    VSTAR = "vstar"
    EX = "ex"
    MEGA_EX = "mega_ex"
    GX = "gx"
    RESTORED = "restored"
    RADIANT = "radiant"
    OTHER = "other"

    @classmethod
    def prize_value(cls, stage: "PokemonStage") -> int:
        """Prize value when KO'd: 3 for VMAX / Mega ex, 2 for V/VSTAR/ex/GX, else 1."""
        if stage in {cls.VMAX, cls.MEGA_EX}:
            return 3
        if stage in {cls.V, cls.VSTAR, cls.EX, cls.GX}:
            return 2
        return 1

    @classmethod
    def stage_index(cls, stage: "PokemonStage") -> int:
        """0 = basic/V, 1 = stage 1, 2 = stage 2/VMAX/VSTAR, 3 = other."""
        if stage in {cls.BASIC, cls.V, cls.EX, cls.GX, cls.RESTORED, cls.RADIANT}:
            return 0
        if stage in {cls.STAGE_1}:
            return 1
        if stage in {cls.STAGE_2, cls.VMAX, cls.VSTAR}:
            return 2
        return 3
