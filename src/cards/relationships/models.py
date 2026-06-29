"""
Core data models for the card relationship graph.

Every relationship is a typed edge between two card nodes.  Nodes carry
minimal denormalised data so graph queries are self-contained.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from src.cards.enums import CardSuperType, EnergyType, PokemonType, Stage, TrainerType

# ---------------------------------------------------------------------------
# Relationship types
# ---------------------------------------------------------------------------


class RelationshipType(str, Enum):
    # Evolution
    EVOLVES_FROM = "evolves_from"
    EVOLVES_TO = "evolves_to"
    # Search / fetch
    SEARCHES_FOR = "searches_for"
    SEARCHED_BY = "searched_by"
    # Energy
    ACCELERATES_ENERGY = "accelerates_energy"
    USES_ENERGY = "uses_energy"
    ENERGY_SYNERGY = "energy_synergy"
    # Healing / protection
    HEALS = "heals"
    PROTECTS = "protects"
    DAMAGE_REDUCTION = "damage_reduction"
    # Switching / retreat
    SWITCHES = "switches"
    # Bench interactions
    BENCH_SUPPORT = "bench_support"
    # Draw / consistency
    DRAW_ENGINE = "draw_engine"
    CONSISTENCY = "consistency"
    # Discard / recovery
    DISCARD_ENGINE = "discard_engine"
    RECOVERY = "recovery"
    # Ability interactions
    ABILITY_SUPPORT = "ability_support"
    ABILITY_COUNTER = "ability_counter"
    # Trainer role by category
    STADIUM_SUPPORT = "stadium_support"
    TOOL_SUPPORT = "tool_support"
    ITEM_SUPPORT = "item_support"
    SUPPORTER_SUPPORT = "supporter_support"
    # Damage
    DAMAGE_BOOST = "damage_boost"
    # Type
    TYPE_SYNERGY = "type_synergy"
    # Status
    STATUS_SYNERGY = "status_synergy"
    SPECIAL_CONDITION = "special_condition"
    # Counter / disruption
    COUNTERS = "counters"
    ANTI_META = "anti_meta"
    LOCK = "lock"
    # Specific roles
    SELF_SETUP = "self_setup"
    FINISHER = "finisher"
    # Unknown
    UNKNOWN = "unknown"


# Inverse relationship map (used to auto-generate bidirectional edges)
INVERSE: dict[RelationshipType, RelationshipType] = {
    RelationshipType.EVOLVES_FROM: RelationshipType.EVOLVES_TO,
    RelationshipType.EVOLVES_TO: RelationshipType.EVOLVES_FROM,
    RelationshipType.SEARCHES_FOR: RelationshipType.SEARCHED_BY,
    RelationshipType.SEARCHED_BY: RelationshipType.SEARCHES_FOR,
    RelationshipType.ACCELERATES_ENERGY: RelationshipType.USES_ENERGY,
    RelationshipType.USES_ENERGY: RelationshipType.ACCELERATES_ENERGY,
    RelationshipType.HEALS: RelationshipType.HEALS,        # symmetric
    RelationshipType.PROTECTS: RelationshipType.PROTECTS,  # symmetric
    RelationshipType.COUNTERS: RelationshipType.COUNTERS,  # not symmetric but self-link
}

# Relationship categories for analytics
DISRUPTION_TYPES = frozenset({
    RelationshipType.COUNTERS,
    RelationshipType.ANTI_META,
    RelationshipType.LOCK,
    RelationshipType.ABILITY_COUNTER,
    RelationshipType.SPECIAL_CONDITION,
})

SUPPORT_TYPES = frozenset({
    RelationshipType.HEALS,
    RelationshipType.PROTECTS,
    RelationshipType.DAMAGE_REDUCTION,
    RelationshipType.DRAW_ENGINE,
    RelationshipType.CONSISTENCY,
    RelationshipType.ACCELERATES_ENERGY,
    RelationshipType.SEARCHES_FOR,
    RelationshipType.BENCH_SUPPORT,
    RelationshipType.SWITCHES,
    RelationshipType.ABILITY_SUPPORT,
    RelationshipType.RECOVERY,
    RelationshipType.STADIUM_SUPPORT,
    RelationshipType.TOOL_SUPPORT,
    RelationshipType.ITEM_SUPPORT,
    RelationshipType.SUPPORTER_SUPPORT,
    RelationshipType.DAMAGE_BOOST,
})


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------


class CardNode(BaseModel):
    """Denormalised card data stored on each graph node."""

    model_config = ConfigDict(frozen=True)

    card_id: str
    name: str
    card_super_type: CardSuperType

    # Pokémon-specific (None for Trainer / Energy)
    pokemon_type: PokemonType | None = None
    stage: Stage | None = None
    hp: int | None = None
    retreat_cost: int | None = None

    # Trainer-specific
    trainer_type: TrainerType | None = None

    # Energy-specific
    energy_type: EnergyType | None = None
    provides: tuple[PokemonType, ...] = ()

    # Raw effect text (pre-parsed)
    effect_text: str = ""


# ---------------------------------------------------------------------------
# Edge
# ---------------------------------------------------------------------------


class CardEdge(BaseModel):
    """A typed, weighted, evidenced relationship between two cards."""

    model_config = ConfigDict(frozen=True)

    source: str               # card_id of the source card
    target: str               # card_id of the target card
    relationship_type: RelationshipType
    weight: float = Field(default=1.0, ge=0.0)
    reason: str = ""
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    evidence: tuple[str, ...] = ()

    @property
    def edge_key(self) -> tuple[str, str, str]:
        return (self.source, self.target, self.relationship_type.value)


# ---------------------------------------------------------------------------
# Card profile
# ---------------------------------------------------------------------------


class CardProfile(BaseModel):
    """Rich relationship summary for a single card, derived from the graph."""

    model_config = ConfigDict(frozen=True)

    card_id: str
    name: str

    # Relationships by role
    supports: tuple[str, ...]           = ()  # cards this card supports
    supported_by: tuple[str, ...]       = ()  # cards that support this card
    counters: tuple[str, ...]           = ()  # cards this card counters
    countered_by: tuple[str, ...]       = ()  # cards that counter this card
    requires: tuple[str, ...]           = ()  # energy / pre-evolutions needed
    required_by: tuple[str, ...]        = ()  # cards that need this one
    recommended_with: tuple[str, ...]   = ()  # top synergy partners
    conflicts_with: tuple[str, ...]     = ()  # cards that conflict

    # Typed synergy bundles
    energy_synergies: tuple[str, ...]   = ()
    trainer_synergies: tuple[str, ...]  = ()
    evolution_family: tuple[str, ...]   = ()

    # Role classification
    primary_role: RelationshipType | None   = None
    secondary_role: RelationshipType | None = None

    # Community membership
    community_id: int | None = None

    # Stats
    total_in_edges: int  = 0
    total_out_edges: int = 0


# ---------------------------------------------------------------------------
# Community
# ---------------------------------------------------------------------------


class Community(BaseModel):
    """A cluster of cards sharing strong mutual synergies."""

    model_config = ConfigDict(frozen=True)

    community_id: int
    core_cards: tuple[str, ...]         # high-degree nodes
    support_cards: tuple[str, ...]      # lower-degree peripheral nodes
    shared_mechanics: tuple[str, ...]   # dominant relationship types
    dominant_energy: PokemonType | None = None
    dominant_pokemon_type: PokemonType | None = None
    key_trainers: tuple[str, ...]       = ()
    size: int                           = 0
    internal_edge_count: int            = 0
    density: float                      = 0.0
