"""
Game setup — build the initial GameState from two 60-card decks.

Handles shuffling, opening hand draw, mulligan loop, prize placement,
and initial active/bench assignment.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from src.cards.enums import RuleBox, Stage, TrainerType
from src.cards.models import EnergyCard, PokemonCard, TrainerCard
from src.game_state.models import CardInstance
from src.game_state.player import PlayerState
from src.game_state.state import GameState
from src.game_state.zones import CardCategory, GameStatus, Zone
from src.game_state.zones import PokemonStage as PStage
from src.simulator.rules import GameRules

if TYPE_CHECKING:
    from src.cards.repository import CardRepository
    from src.simulator.randomizer import Randomizer


def build_initial_state(
    deck_a: list[int],
    deck_b: list[int],
    repository: CardRepository,
    randomizer: Randomizer,
    rules: GameRules,
) -> GameState:
    """Construct a fully-set-up GameState ready for turn 1."""
    if len(deck_a) != rules.deck_size or len(deck_b) != rules.deck_size:
        raise ValueError(
            f"Both decks must contain {rules.deck_size} cards, "
            f"got {len(deck_a)} and {len(deck_b)}"
        )

    # 1. Instantiate every card as a CardInstance (one per slot in deck).
    instances: dict[str, CardInstance] = {}
    p0_deck_ids = _instantiate_deck(deck_a, 0, repository, instances)
    p1_deck_ids = _instantiate_deck(deck_b, 1, repository, instances)

    # 2. Shuffle decks
    p0_deck_ids = randomizer.shuffle(p0_deck_ids)
    p1_deck_ids = randomizer.shuffle(p1_deck_ids)

    # 3. Coin flip → who goes first (player 0)
    first_player = 0 if randomizer.coin_flip() else 1
    if first_player == 1:
        # Swap so current_player=0 always goes first
        p0_deck_ids, p1_deck_ids = p1_deck_ids, p0_deck_ids

    # 4. Draw opening hands with mulligan
    p0_hand, p0_deck, p0_mulls = _draw_with_mulligan(
        p0_deck_ids, repository, instances, randomizer, rules.starting_hand_size, rules,
    )
    p1_hand, p1_deck, p1_mulls = _draw_with_mulligan(
        p1_deck_ids, repository, instances, randomizer, rules.starting_hand_size, rules,
    )

    # Mulligan bonus: opposing player draws +1 per mulligan
    if rules.mulligan_bonus_card:
        for _ in range(p0_mulls):
            if p1_deck:
                p1_hand.append(p1_deck.pop(0))
        for _ in range(p1_mulls):
            if p0_deck:
                p0_hand.append(p0_deck.pop(0))

    # 5. Place prizes (top 6 cards of remaining deck)
    p0_prizes = p0_deck[: rules.prize_count]
    p0_deck = p0_deck[rules.prize_count :]
    p1_prizes = p1_deck[: rules.prize_count]
    p1_deck = p1_deck[rules.prize_count :]

    # 6. Choose Active and Bench: first basic Pokémon from hand goes Active,
    #    remaining basics go to bench (up to bench size).
    p0_active, p0_bench, p0_hand = _choose_initial_pokemon(
        p0_hand, repository, instances, rules,
    )
    p1_active, p1_bench, p1_hand = _choose_initial_pokemon(
        p1_hand, repository, instances, rules,
    )

    # 7. Update CardInstance zones
    instances = _set_zones(
        instances,
        deck={0: p0_deck, 1: p1_deck},
        hand={0: p0_hand, 1: p1_hand},
        prize={0: p0_prizes, 1: p1_prizes},
        active={0: p0_active, 1: p1_active},
        bench={0: p0_bench, 1: p1_bench},
    )

    # 8. Build PlayerStates
    p0 = PlayerState(
        player_id=0,
        active=p0_active,
        bench=tuple(p0_bench),
        bench_count=len(p0_bench),
        hand=tuple(p0_hand),
        hand_count=len(p0_hand),
        deck_size=len(p0_deck),
        deck_order=tuple(p0_deck),
        discard=(),
        discard_count=0,
        prizes=tuple(p0_prizes),
        prizes_remaining=len(p0_prizes),
    )
    p1 = PlayerState(
        player_id=1,
        active=p1_active,
        bench=tuple(p1_bench),
        bench_count=len(p1_bench),
        hand=tuple(p1_hand),
        hand_count=len(p1_hand),
        deck_size=len(p1_deck),
        deck_order=tuple(p1_deck),
        discard=(),
        discard_count=0,
        prizes=tuple(p1_prizes),
        prizes_remaining=len(p1_prizes),
    )

    return GameState(
        turn_number=1,
        current_player=0,
        game_status=GameStatus.ONGOING,
        players=(p0, p1),
        card_instances=instances,
    )


# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------

def _instantiate_deck(
    deck: list[int], owner: int,
    repo: CardRepository, instances: dict[str, CardInstance],
) -> list[str]:
    """Create one CardInstance per card_id and return ordered instance_ids."""
    ids: list[str] = []
    for card_id in deck:
        card = repo.get_by_id(card_id)
        if card is None:
            continue
        inst = _make_instance(card, owner)
        instances[inst.instance_id] = inst
        ids.append(inst.instance_id)
    return ids


def _make_instance(card, owner: int) -> CardInstance:
    iid = str(uuid.uuid4())
    if isinstance(card, PokemonCard):
        return CardInstance(
            instance_id=iid, card_id=str(card.card_id), card_name=card.name,
            owner=owner, zone=Zone.DECK, category=CardCategory.POKEMON,
            base_hp=card.hp or 60,
            stage=_pokemon_stage(card),
            prize_value=PStage.prize_value(_pokemon_stage(card)),
        )
    if isinstance(card, TrainerCard):
        cat = {
            TrainerType.ITEM:         CardCategory.TRAINER_ITEM,
            TrainerType.SUPPORTER:    CardCategory.TRAINER_SUPPORTER,
            TrainerType.STADIUM:      CardCategory.TRAINER_STADIUM,
            TrainerType.POKEMON_TOOL: CardCategory.TRAINER_TOOL,
        }.get(card.trainer_type, CardCategory.TRAINER_ITEM)
        return CardInstance(
            instance_id=iid, card_id=str(card.card_id), card_name=card.name,
            owner=owner, zone=Zone.DECK, category=cat,
        )
    if isinstance(card, EnergyCard):
        cat = (CardCategory.ENERGY_BASIC
                if getattr(card, "energy_type", None) and card.energy_type.value == "Basic"
                else CardCategory.ENERGY_SPECIAL)
        return CardInstance(
            instance_id=iid, card_id=str(card.card_id), card_name=card.name,
            owner=owner, zone=Zone.DECK, category=cat,
        )
    # Fallback
    return CardInstance(
        instance_id=iid, card_id=str(getattr(card, "card_id", 0)),
        card_name=getattr(card, "name", ""), owner=owner, zone=Zone.DECK,
    )


def _pokemon_stage(card: PokemonCard) -> PStage:
    """Map a static PokemonCard to its runtime PokemonStage.

    Mega Pokémon-ex give 3 prizes; Pokémon-ex give 2; everything else
    follows the printed evolution stage.  Comparison uses RuleBox enum
    members directly (never string equality on .value).
    """
    rule_box = getattr(card, "rule_box", None)
    if rule_box == RuleBox.MEGA_POKEMON_EX:
        return PStage.MEGA_EX
    if rule_box == RuleBox.POKEMON_EX:
        return PStage.EX
    return {
        Stage.BASIC:   PStage.BASIC,
        Stage.STAGE_1: PStage.STAGE_1,
        Stage.STAGE_2: PStage.STAGE_2,
    }.get(card.stage, PStage.BASIC)


def _draw_with_mulligan(
    deck: list[str], repo: CardRepository,
    instances: dict[str, CardInstance], randomizer: Randomizer,
    hand_size: int, rules: GameRules,
) -> tuple[list[str], list[str], int]:
    """Draw hand_size cards; mulligan until at least one basic Pokémon is present."""
    mulls = 0
    for _ in range(rules.max_mulligans):
        hand = deck[:hand_size]
        rest = deck[hand_size:]
        if _has_basic(hand, repo, instances):
            return hand, rest, mulls
        # Mulligan: put hand back, shuffle, redraw
        deck = randomizer.shuffle(list(hand) + list(rest))
        mulls += 1
    # Failed mulligan loop — just return whatever we have
    return deck[:hand_size], deck[hand_size:], mulls


def _has_basic(
    hand: list[str], repo: CardRepository,
    instances: dict[str, CardInstance],
) -> bool:
    for iid in hand:
        inst = instances.get(iid)
        if inst is None:
            continue
        card = repo.get_by_id(int(inst.card_id))
        if isinstance(card, PokemonCard) and card.stage == Stage.BASIC:
            return True
    return False


def _choose_initial_pokemon(
    hand: list[str], repo: CardRepository,
    instances: dict[str, CardInstance], rules: GameRules,
) -> tuple[str | None, list[str], list[str]]:
    """Pick active + bench from the basic Pokémon in the hand."""
    active: str | None = None
    bench: list[str] = []
    rest: list[str] = []
    for iid in hand:
        inst = instances.get(iid)
        if inst is None:
            rest.append(iid)
            continue
        card = repo.get_by_id(int(inst.card_id))
        is_basic_pokemon = isinstance(card, PokemonCard) and card.stage == Stage.BASIC
        if is_basic_pokemon and active is None:
            active = iid
        elif is_basic_pokemon and len(bench) < rules.bench_size:
            bench.append(iid)
        else:
            rest.append(iid)
    return active, bench, rest


def _set_zones(
    instances: dict[str, CardInstance],
    *,
    deck: dict[int, list[str]],
    hand: dict[int, list[str]],
    prize: dict[int, list[str]],
    active: dict[int, str | None],
    bench: dict[int, list[str]],
) -> dict[str, CardInstance]:
    out = dict(instances)
    for player_id in (0, 1):
        for iid in deck[player_id]:
            if iid in out:
                out[iid] = out[iid].with_zone(Zone.DECK)
        for iid in hand[player_id]:
            if iid in out:
                out[iid] = out[iid].with_zone(Zone.HAND)
        for iid in prize[player_id]:
            if iid in out:
                out[iid] = out[iid].with_zone(Zone.PRIZE)
        if active[player_id] and active[player_id] in out:
            out[active[player_id]] = out[active[player_id]].with_zone(Zone.ACTIVE)
        for iid in bench[player_id]:
            if iid in out:
                out[iid] = out[iid].with_zone(Zone.BENCH)
    return out
