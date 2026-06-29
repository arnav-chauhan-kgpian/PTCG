"""
Raw deck metrics — counts, distributions, averages.

All computations are O(60) and produce a frozen DeckMetrics object.
"""

from __future__ import annotations

from collections import defaultdict

from pydantic import BaseModel, ConfigDict

from src.cards.enums import (
    EnergyType,
    RuleBox,
    Stage,
    TrainerType,
)
from src.cards.models import EnergyCard, PokemonCard, TrainerCard
from src.decks.models import Deck


class DeckMetrics(BaseModel):
    """All raw metrics for a 60-card deck. Immutable."""

    model_config = ConfigDict(frozen=True)

    # --- Counts ---
    total_cards: int
    pokemon_count: int
    trainer_count: int
    energy_count: int

    basic_pokemon_count: int
    stage1_count: int
    stage2_count: int

    supporter_count: int
    item_count: int
    stadium_count: int
    tool_count: int

    basic_energy_count: int
    special_energy_count: int

    # Rule-box / prize-liability
    rule_box_count: int          # ex/V/VMAX/etc (each worth 2 prizes when KO'd)
    ace_spec_count: int

    # --- HP ---
    avg_hp: float
    max_hp: int
    min_hp: int

    # --- Damage ---
    avg_damage: float
    max_damage: int
    avg_attack_cost: float       # average energy tokens per attack

    # --- Retreat ---
    avg_retreat: float
    retreat_distribution: dict[int, int]   # retreat_cost → count

    # --- Energy curve ---
    attack_cost_distribution: dict[int, int]  # total_cost → frequency

    # --- Type distributions ---
    pokemon_type_distribution: dict[str, int]   # PokemonType.value → count
    energy_type_distribution: dict[str, int]    # PokemonType.value → count provided
    weakness_distribution: dict[str, int]       # PokemonType.value → count
    resistance_distribution: dict[str, int]     # PokemonType.value → count

    # --- Support power ---
    draw_power: int       # count of cards with draw effects
    search_power: int     # count of cards with deck-search effects
    recovery_score: int   # count of retrieval cards
    disruption_score: int # count of disruption cards
    healing_score: int    # count of healing cards
    switch_count: int     # count of switch/retreat helpers
    energy_acceleration: int  # count of energy-attach-outside-turn effects

    # --- Prize liability ---
    prize_liability_score: float   # higher = more 2-prize targets exposed

    # --- Bench ---
    bench_support_count: int

    # --- Unique Pokémon lines ---
    unique_pokemon_names: int
    unique_evolution_lines: int


def compute_metrics(deck: Deck) -> DeckMetrics:
    """Compute all metrics from a Deck object."""

    # --- Tallies ---
    pokemon_count = trainer_count = energy_count = 0
    basic_count = stage1_count = stage2_count = 0
    supporter_count = item_count = stadium_count = tool_count = 0
    basic_energy_count = special_energy_count = 0
    rule_box_count = ace_spec_count = 0

    hp_values: list[int] = []
    damage_values: list[int] = []
    attack_costs: list[int] = []
    retreat_costs: list[int] = []

    retreat_dist: dict[int, int] = defaultdict(int)
    attack_cost_dist: dict[int, int] = defaultdict(int)
    pokemon_type_dist: dict[str, int] = defaultdict(int)
    energy_type_dist: dict[str, int] = defaultdict(int)
    weakness_dist: dict[str, int] = defaultdict(int)
    resistance_dist: dict[str, int] = defaultdict(int)

    draw_power = search_power = recovery_score = 0
    disruption_score = healing_score = switch_count = 0
    energy_acceleration = bench_support_count = 0

    pokemon_names: set[str] = set()
    evolution_roots: set[str] = set()

    for slot in deck.slots:
        card = slot.card
        n = slot.count

        # Rule box
        if card.rule_box != RuleBox.NONE:
            rule_box_count += n
        if card.rule_box == RuleBox.ACE_SPEC:
            ace_spec_count += n

        if isinstance(card, PokemonCard):
            pokemon_count += n
            pokemon_names.add(card.name)

            if card.stage == Stage.BASIC:
                basic_count += n
            elif card.stage == Stage.STAGE_1:
                stage1_count += n
            elif card.stage == Stage.STAGE_2:
                stage2_count += n

            hp_values.extend([card.hp] * n)
            pokemon_type_dist[card.pokemon_type.value] += n

            if card.weakness:
                weakness_dist[card.weakness.energy_type.value] += n
            if card.resistance:
                resistance_dist[card.resistance.energy_type.value] += n

            retreat_costs.extend([card.retreat_cost] * n)
            retreat_dist[card.retreat_cost] += n

            for attack in card.attacks:
                cost = attack.cost.total_count
                dmg = attack.damage.base
                attack_costs.append(cost)
                attack_cost_dist[cost] += 1
                if dmg > 0:
                    damage_values.append(dmg)

            # Effect-based counters (Pokémon abilities)
            if card.ability:
                text = card.ability.effect.lower()
                _tally_effect(text, draw=draw_power, search=search_power,
                              recovery=recovery_score, disruption=disruption_score,
                              healing=healing_score, switch=switch_count,
                              energy_acc=energy_acceleration, bench=bench_support_count)
                draw_power, search_power, recovery_score, disruption_score, \
                healing_score, switch_count, energy_acceleration, bench_support_count = \
                    _tally_effect_counts(
                        text, draw_power, search_power, recovery_score,
                        disruption_score, healing_score, switch_count,
                        energy_acceleration, bench_support_count,
                    )

            if card.previous_stage is None and card.stage == Stage.BASIC:
                evolution_roots.add(card.name)

        elif isinstance(card, TrainerCard):
            trainer_count += n
            tt = card.trainer_type
            if tt == TrainerType.SUPPORTER:
                supporter_count += n
            elif tt == TrainerType.ITEM:
                item_count += n
            elif tt == TrainerType.STADIUM:
                stadium_count += n
            elif tt == TrainerType.POKEMON_TOOL:
                tool_count += n

            text = card.effect.lower()
            draw_power, search_power, recovery_score, disruption_score, \
            healing_score, switch_count, energy_acceleration, bench_support_count = \
                _tally_effect_counts(
                    text, draw_power, search_power, recovery_score,
                    disruption_score, healing_score, switch_count,
                    energy_acceleration, bench_support_count,
                    multiplier=n,
                )

        elif isinstance(card, EnergyCard):
            energy_count += n
            if card.energy_type == EnergyType.BASIC:
                basic_energy_count += n
            else:
                special_energy_count += n
            for pt in card.provides:
                energy_type_dist[pt.value] += n

    # Aggregate
    avg_hp = sum(hp_values) / len(hp_values) if hp_values else 0.0
    max_hp = max(hp_values) if hp_values else 0
    min_hp = min(hp_values) if hp_values else 0

    avg_damage = sum(damage_values) / len(damage_values) if damage_values else 0.0
    max_damage = max(damage_values) if damage_values else 0

    avg_attack_cost = sum(attack_costs) / len(attack_costs) if attack_costs else 0.0
    avg_retreat = sum(retreat_costs) / len(retreat_costs) if retreat_costs else 0.0

    prize_liability = rule_box_count / max(pokemon_count, 1)

    # Identify unique evolution lines (count basic Pokémon that have evolutions or ARE evolution)
    unique_evo_lines = len(evolution_roots)

    return DeckMetrics(
        total_cards=deck.total_count,
        pokemon_count=pokemon_count,
        trainer_count=trainer_count,
        energy_count=energy_count,
        basic_pokemon_count=basic_count,
        stage1_count=stage1_count,
        stage2_count=stage2_count,
        supporter_count=supporter_count,
        item_count=item_count,
        stadium_count=stadium_count,
        tool_count=tool_count,
        basic_energy_count=basic_energy_count,
        special_energy_count=special_energy_count,
        rule_box_count=rule_box_count,
        ace_spec_count=ace_spec_count,
        avg_hp=round(avg_hp, 1),
        max_hp=max_hp,
        min_hp=min_hp,
        avg_damage=round(avg_damage, 1),
        max_damage=max_damage,
        avg_attack_cost=round(avg_attack_cost, 2),
        avg_retreat=round(avg_retreat, 2),
        retreat_distribution=dict(retreat_dist),
        attack_cost_distribution=dict(attack_cost_dist),
        pokemon_type_distribution=dict(pokemon_type_dist),
        energy_type_distribution=dict(energy_type_dist),
        weakness_distribution=dict(weakness_dist),
        resistance_distribution=dict(resistance_dist),
        draw_power=draw_power,
        search_power=search_power,
        recovery_score=recovery_score,
        disruption_score=disruption_score,
        healing_score=healing_score,
        switch_count=switch_count,
        energy_acceleration=energy_acceleration,
        bench_support_count=bench_support_count,
        prize_liability_score=round(prize_liability, 3),
        unique_pokemon_names=len(pokemon_names),
        unique_evolution_lines=unique_evo_lines,
    )


# --- Effect keyword tallying ---

_DRAW_KW = ("draw", "draw a card", "draw cards", "draw until")
_SEARCH_KW = ("search your deck", "look at the top", "put a card from your deck")
_RECOVERY_KW = ("retrieve", "return", "from your discard", "from your discard pile", "recover")
_DISRUPTION_KW = ("discard", "opponent's hand", "shuffle", "skip", "can't use", "blocked", "lock")
_HEAL_KW = ("heal", "remove damage", "remove.*damage counter", "take.*damage off")
_SWITCH_KW = ("switch", "retreat", "gust", "move.*active")
_ACCEL_KW = ("attach.*energy", "attach an energy", "energy from", "accelerate")
_BENCH_KW = ("bench", "benched", "put.*bench")


def _tally_effect_counts(
    text: str,
    draw: int, search: int, recovery: int, disruption: int,
    healing: int, switch: int, energy_acc: int, bench: int,
    multiplier: int = 1,
) -> tuple[int, int, int, int, int, int, int, int]:
    if any(k in text for k in _DRAW_KW):
        draw += multiplier
    if any(k in text for k in _SEARCH_KW):
        search += multiplier
    if any(k in text for k in _RECOVERY_KW):
        recovery += multiplier
    if any(k in text for k in _DISRUPTION_KW):
        disruption += multiplier
    if any(k in text for k in _HEAL_KW):
        healing += multiplier
    if any(k in text for k in _SWITCH_KW):
        switch += multiplier
    if any(k in text for k in _ACCEL_KW):
        energy_acc += multiplier
    if any(k in text for k in _BENCH_KW):
        bench += multiplier
    return draw, search, recovery, disruption, healing, switch, energy_acc, bench


def _tally_effect(text: str, **kwargs: int) -> None:
    """No-op stub to satisfy type checker for ability path."""
    pass
