"""
Immutable CardInstance — runtime wrapper around a static card definition.

Each physical card in play is represented by a unique CardInstance, which
carries all mutable runtime state (damage, energy, conditions, zone, etc.)
while leaving the static card definition untouched in the card repository.
"""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field

from src.game_state.zones import (
    CardCategory,
    EnergyTypeCode,
    PokemonStage,
    SpecialCondition,
    Zone,
)


class EnergyAttachment(BaseModel):
    """A single energy card attached to a Pokémon."""
    model_config = ConfigDict(frozen=True)

    instance_id: str
    card_id: str
    card_name: str
    energy_type: EnergyTypeCode = EnergyTypeCode.COLORLESS
    provides_count: int = 1


class CardInstance(BaseModel):
    """
    Immutable runtime representation of one physical card in the game.

    Produced by a factory when a card enters the game; updated via
    ``model_copy(update=...)`` to produce new immutable states.
    """
    model_config = ConfigDict(frozen=True)

    # Identity
    instance_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    card_id: str                    # static card DB reference
    card_name: str
    owner: int                      # 0 or 1
    zone: Zone = Zone.DECK
    category: CardCategory = CardCategory.POKEMON

    # Pokémon HP tracking
    base_hp: int = 0                # printed HP
    hp_modifier: int = 0            # temporary HP buffs/nerfs from effects
    damage_taken: int = 0           # total damage placed on this Pokémon

    # Pokémon stage & evolution chain
    stage: PokemonStage = PokemonStage.BASIC
    prize_value: int = 1            # 1 for regular, 2 for V/ex/GX
    previous_stage_instance_id: str | None = None

    # Attachments (stored as instance_ids, resolved via GameState.card_instances)
    attached_energy_ids: tuple[str, ...] = ()
    attached_tool_id: str | None = None

    # Status
    special_conditions: tuple[SpecialCondition, ...] = ()

    # Turn-tracking flags
    turn_entered_play: int = 0
    has_attacked: bool = False
    has_retreated: bool = False
    is_evolved_this_turn: bool = False
    ability_used: bool = False

    # Arbitrary key-value effect flags ("key=value")
    effect_flags: tuple[str, ...] = ()

    # ------------------------------------------------------------------ #
    # Computed properties
    # ------------------------------------------------------------------ #

    @property
    def max_hp(self) -> int:
        return max(0, self.base_hp + self.hp_modifier)

    @property
    def remaining_hp(self) -> int:
        return max(0, self.max_hp - self.damage_taken)

    @property
    def hp_ratio(self) -> float:
        if self.max_hp == 0:
            return 1.0
        return self.remaining_hp / self.max_hp

    @property
    def is_knocked_out(self) -> bool:
        return self.max_hp > 0 and self.damage_taken >= self.max_hp

    @property
    def has_condition(self) -> bool:
        return len(self.special_conditions) > 0

    def has_flag(self, key: str) -> bool:
        return any(f.startswith(f"{key}=") or f == key for f in self.effect_flags)

    def get_flag(self, key: str) -> str | None:
        for f in self.effect_flags:
            if f.startswith(f"{key}="):
                return f.split("=", 1)[1]
            if f == key:
                return ""
        return None

    # ------------------------------------------------------------------ #
    # Immutable update helpers
    # ------------------------------------------------------------------ #

    def with_zone(self, zone: Zone) -> CardInstance:
        return self.model_copy(update={"zone": zone})

    def with_damage(self, damage_taken: int) -> CardInstance:
        return self.model_copy(update={"damage_taken": max(0, damage_taken)})

    def with_added_damage(self, amount: int) -> CardInstance:
        return self.with_damage(self.damage_taken + amount)

    def with_condition(self, condition: SpecialCondition) -> CardInstance:
        if condition in self.special_conditions:
            return self
        return self.model_copy(
            update={"special_conditions": self.special_conditions + (condition,)}
        )

    def without_conditions(self) -> CardInstance:
        return self.model_copy(update={"special_conditions": ()})

    def with_energy_attached(self, instance_id: str) -> CardInstance:
        return self.model_copy(
            update={"attached_energy_ids": self.attached_energy_ids + (instance_id,)}
        )

    def without_energy(self, instance_id: str) -> CardInstance:
        return self.model_copy(
            update={
                "attached_energy_ids": tuple(
                    eid for eid in self.attached_energy_ids if eid != instance_id
                )
            }
        )

    def with_flag(self, key: str, value: str = "") -> CardInstance:
        tag = f"{key}={value}" if value else key
        flags = tuple(
            f for f in self.effect_flags
            if not (f.startswith(f"{key}=") or f == key)
        )
        return self.model_copy(update={"effect_flags": flags + (tag,)})

    def without_flag(self, key: str) -> CardInstance:
        flags = tuple(
            f for f in self.effect_flags
            if not (f.startswith(f"{key}=") or f == key)
        )
        return self.model_copy(update={"effect_flags": flags})

    # ------------------------------------------------------------------ #
    # Factory helpers
    # ------------------------------------------------------------------ #

    @classmethod
    def create_pokemon(
        cls,
        card_id: str,
        card_name: str,
        owner: int,
        base_hp: int,
        stage: PokemonStage = PokemonStage.BASIC,
        prize_value: int = 1,
        instance_id: str | None = None,
    ) -> CardInstance:
        return cls(
            instance_id=instance_id or str(uuid.uuid4()),
            card_id=card_id,
            card_name=card_name,
            owner=owner,
            zone=Zone.HAND,
            category=CardCategory.POKEMON,
            base_hp=base_hp,
            stage=stage,
            prize_value=prize_value,
        )

    @classmethod
    def create_trainer(
        cls,
        card_id: str,
        card_name: str,
        owner: int,
        category: CardCategory = CardCategory.TRAINER_ITEM,
        instance_id: str | None = None,
    ) -> CardInstance:
        return cls(
            instance_id=instance_id or str(uuid.uuid4()),
            card_id=card_id,
            card_name=card_name,
            owner=owner,
            zone=Zone.HAND,
            category=category,
        )

    @classmethod
    def create_energy(
        cls,
        card_id: str,
        card_name: str,
        owner: int,
        energy_type: EnergyTypeCode = EnergyTypeCode.COLORLESS,
        is_basic: bool = True,
        instance_id: str | None = None,
    ) -> CardInstance:
        return cls(
            instance_id=instance_id or str(uuid.uuid4()),
            card_id=card_id,
            card_name=card_name,
            owner=owner,
            zone=Zone.HAND,
            category=CardCategory.ENERGY_BASIC if is_basic else CardCategory.ENERGY_SPECIAL,
        )
