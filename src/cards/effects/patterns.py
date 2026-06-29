"""
Compiled regex patterns and the Rule namedtuple.

Each Rule has:
  name        — unique string identifier for debugging
  pattern     — compiled regex (re.IGNORECASE | re.DOTALL)
  factory     — callable(Match, str) → Effect
  priority    — lower = tried first (default 100)

Patterns are NOT compiled here — they're compiled lazily in registry.py
because we want tests to import this module without side-effects.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from src.cards.effects import models as M
from src.cards.effects.actions import ActionTag, Frequency, Target, Zone
from src.cards.effects.grammar import (
    ENERGY_TYPE,
    NUM_DIGIT,
    NUM_WORD,
    STATUS_NAME,
    UP_TO_N,
)
from src.cards.enums import PokemonType, StatusCondition

# ---------------------------------------------------------------------------
# Helpers shared across factory functions
# ---------------------------------------------------------------------------


_WORD_TO_INT: dict[str, int] = {
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4,
    "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}


def _int(raw: str | None, default: int = 1) -> int:
    if raw is None:
        return default
    raw = raw.strip().lower()
    return _WORD_TO_INT.get(raw, int(raw) if raw.isdigit() else default)


def _energy_type(raw: str | None) -> PokemonType | None:
    if raw is None:
        return None
    _MAP = {
        "{G}": PokemonType.GRASS, "{R}": PokemonType.FIRE, "{W}": PokemonType.WATER,
        "{L}": PokemonType.LIGHTNING, "{P}": PokemonType.PSYCHIC, "{F}": PokemonType.FIGHTING,
        "{D}": PokemonType.DARK, "{M}": PokemonType.METAL, "{C}": PokemonType.COLORLESS,
        "竜": PokemonType.DRAGON,
    }
    return _MAP.get(raw.strip())


def _status(raw: str) -> StatusCondition:
    _MAP = {
        "burned": StatusCondition.BURNED, "paralyzed": StatusCondition.PARALYZED,
        "poisoned": StatusCondition.POISONED, "asleep": StatusCondition.ASLEEP,
        "confused": StatusCondition.CONFUSED,
    }
    return _MAP.get(raw.lower().strip(), StatusCondition.BURNED)


def _target_opp(text: str) -> Target:
    """Determine opponent target from text."""
    tl = text.lower()
    if "bench" in tl:
        return Target.BENCHED_OPP
    return Target.ACTIVE_OPP


# ---------------------------------------------------------------------------
# Rule dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Rule:
    """A single parsing rule."""

    name: str
    pattern: re.Pattern[str]
    factory: Callable[[re.Match[str], str], M.Effect]
    priority: int = 100

    def match(self, text: str) -> re.Match[str] | None:
        return self.pattern.search(text)


# ---------------------------------------------------------------------------
# Rule factories  (alphabetical by category)
# ---------------------------------------------------------------------------

FLAGS = re.IGNORECASE | re.DOTALL


def _compile(raw: str) -> re.Pattern[str]:
    return re.compile(raw, FLAGS)


# ---- Draw -----------------------------------------------------------------

def _draw_n(m: re.Match, raw: str) -> M.DrawCards:
    return M.DrawCards(count=_int(m.group("n")), raw_text=raw)


def _draw_until(m: re.Match, raw: str) -> M.DrawCards:
    return M.DrawCards(until_hand_size=_int(m.group("n")), raw_text=raw)


def _draw_card(m: re.Match, raw: str) -> M.DrawCards:
    return M.DrawCards(count=1, raw_text=raw)


DRAW_RULES: list[Rule] = [
    Rule(
        "draw_n_cards",
        _compile(r"\bDraw (?P<n>" + NUM_WORD + r") cards?\b"),
        _draw_n,
        priority=10,
    ),
    Rule(
        "draw_until_hand",
        _compile(r"\bDraw cards? until you have (?P<n>" + NUM_DIGIT + r") cards? in your hand\b"),
        _draw_until,
        priority=11,
    ),
    Rule(
        "draw_a_card",
        _compile(r"\bDraw a card\b"),
        _draw_card,
        priority=12,
    ),
    Rule(
        "each_player_draws",
        _compile(r"\bEach player draws? (?P<n>" + NUM_WORD + r") cards?\b"),
        lambda m, raw: M.DrawCards(count=_int(m.group("n")), raw_text=raw),
        priority=13,
    ),
]

# ---- Heal -----------------------------------------------------------------

def _heal_n(m: re.Match, raw: str) -> M.HealEffect:
    amt = _int(m.group("n"), 0) if m.group("n") else None
    tgt = raw.lower()
    if "benched" in tgt:
        target = Target.BENCHED_SELF
    elif "active" in tgt:
        target = Target.ACTIVE_SELF
    elif "this pokémon" in tgt or "this pokemon" in tgt:
        target = Target.SELF
    else:
        target = Target.ANY_SELF
    return M.HealEffect(amount=amt, target=target, raw_text=raw)


def _heal_all(m: re.Match, raw: str) -> M.HealEffect:
    return M.HealEffect(amount=None, target=Target.ANY_SELF, raw_text=raw)


HEAL_RULES: list[Rule] = [
    Rule(
        "heal_n_damage",
        _compile(r"\bHeal (?P<n>" + NUM_DIGIT + r") damage\b"),
        _heal_n,
        priority=20,
    ),
    Rule(
        "heal_all_damage",
        _compile(r"\bHeal all damage from\b"),
        _heal_all,
        priority=21,
    ),
    Rule(
        "heal_self_n",
        _compile(r"\bheal (?P<n>" + NUM_DIGIT + r") damage from this Pok[eé]mon\b"),
        lambda m, raw: M.HealEffect(amount=_int(m.group("n")), target=Target.SELF, raw_text=raw),
        priority=22,
    ),
]

# ---- Status conditions ----------------------------------------------------

def _status_effect(m: re.Match, raw: str) -> M.StatusConditionEffect:
    sc = _status(m.group("sc"))
    tgt_text = raw.lower()
    if "this pokémon" in tgt_text or "this pokemon" in tgt_text:
        tgt = Target.SELF
    else:
        tgt = Target.ACTIVE_OPP
    return M.StatusConditionEffect(condition=sc, target=tgt, raw_text=raw)


STATUS_RULES: list[Rule] = [
    Rule(
        "inflict_status_active",
        _compile(
            r"(?:is now|are now|now becomes?|make your opponent['']s Active Pok[eé]mon)\s*"
            r"(?P<sc>Burned|Paralyzed|Poisoned|Asleep|Confused)"
        ),
        _status_effect,
        priority=30,
    ),
    Rule(
        "self_asleep",
        _compile(r"[Tt]his Pok[eé]mon is now (?P<sc>Asleep|Confused|Poisoned|Burned|Paralyzed)"),
        lambda m, raw: M.StatusConditionEffect(
            condition=_status(m.group("sc")), target=Target.SELF,
            action_type=ActionTag.SELF_STATUS, raw_text=raw
        ),
        priority=31,
    ),
]

# ---- Discard energy from self ---------------------------------------------

def _discard_energy_self(m: re.Match, raw: str) -> M.DiscardEffect:
    count_str = m.groupdict().get("n") or m.groupdict().get("count")
    count = None if (count_str and count_str.lower() == "all") else _int(count_str, 1)
    etype = _energy_type(m.groupdict().get("etype"))
    return M.DiscardEffect(
        source=Target.SELF, zone=Zone.ACTIVE,
        count=count, energy_type=etype, card_type="energy", raw_text=raw,
    )


def _discard_energy_opp(m: re.Match, raw: str) -> M.DiscardEffect:
    count_str = m.groupdict().get("n")
    count = _int(count_str, 1)
    etype = _energy_type(m.groupdict().get("etype"))
    return M.DiscardEffect(
        source=Target.ACTIVE_OPP, zone=Zone.ACTIVE,
        count=count, energy_type=etype, card_type="energy",
        action_type=ActionTag.DISCARD_ENERGY, raw_text=raw,
    )


DISCARD_RULES: list[Rule] = [
    Rule(
        "discard_n_energy_self",
        _compile(
            r"[Dd]iscard (?P<n>" + NUM_WORD + r"|all) "
            r"(?:(?P<etype>" + ENERGY_TYPE + r") )?Energy from this Pok[eé]mon"
        ),
        _discard_energy_self,
        priority=40,
    ),
    Rule(
        "discard_all_energy_self",
        _compile(r"[Dd]iscard all Energy from this Pok[eé]mon"),
        lambda m, raw: M.DiscardEffect(
            source=Target.SELF, count=None, energy_type=None,
            card_type="energy", raw_text=raw,
        ),
        priority=41,
    ),
    Rule(
        "discard_energy_opp_active",
        _compile(
            r"[Dd]iscard (?:(?P<n>" + NUM_WORD + r") )?(?:an? )?Energy from "
            r"your opponent['']s Active Pok[eé]mon"
        ),
        _discard_energy_opp,
        priority=42,
    ),
    Rule(
        "discard_hand_draw",
        _compile(r"[Dd]iscard your hand and draw (?P<n>" + NUM_DIGIT + r") cards?"),
        lambda m, raw: M.CompositeEffect(
            steps=(
                M.DiscardEffect(
                    source=Target.ACTIVE_SELF, zone=Zone.HAND,
                    card_type="hand", raw_text=raw,
                    action_type=ActionTag.DISCARD_HAND,
                ),
                M.DrawCards(count=_int(m.group("n")), raw_text=raw),
            ),
            raw_text=raw,
        ),
        priority=43,
    ),
    Rule(
        "discard_top_n_deck_self",
        _compile(r"[Dd]iscard the top (?P<n>" + NUM_DIGIT + r") cards? of your deck"),
        lambda m, raw: M.MillEffect(count=_int(m.group("n")), who=Target.ACTIVE_SELF, raw_text=raw),
        priority=44,
    ),
    Rule(
        "discard_top_n_deck_opp",
        _compile(r"[Dd]iscard the top (?P<n>" + NUM_DIGIT + r") cards? of your opponent['']s deck"),
        lambda m, raw: M.MillEffect(count=_int(m.group("n")), who=Target.ACTIVE_OPP, raw_text=raw),
        priority=45,
    ),
    Rule(
        "discard_stadium",
        _compile(r"[Dd]iscard (?:a|the) Stadium(?: in play)?"),
        lambda m, raw: M.StadiumInteraction(operation="discard", raw_text=raw),
        priority=46,
    ),
    Rule(
        "discard_tool",
        _compile(r"[Dd]iscard (?:all )?Pok[eé]mon Tools?(?: attached| from| and)"),
        lambda m, raw: M.ToolInteraction(operation="discard", target=Target.ANY_OPP, raw_text=raw),
        priority=47,
    ),
    Rule(
        "discard_random_opp_hand",
        _compile(r"[Dd]iscard a random card from your opponent['']s hand"),
        lambda m, raw: M.DiscardEffect(
            source=Target.ACTIVE_OPP, zone=Zone.HAND,
            card_type="random", action_type=ActionTag.DISCARD_RANDOM, raw_text=raw,
        ),
        priority=48,
    ),
]

# ---- Search deck ----------------------------------------------------------

def _search_deck(m: re.Match, raw: str) -> M.SearchDeck:
    groups = m.groupdict()
    count_raw = groups.get("count") or groups.get("n") or "1"
    count = None if count_raw is None else _int(count_raw, 1)
    etype = _energy_type(groups.get("etype"))
    card_type = groups.get("ctype") or "card"
    attach = "attach" in raw.lower() and "to" in raw.lower()
    return M.SearchDeck(
        card_type=card_type.strip(),
        count=count,
        destination=Zone.BENCH if "Bench" in raw else Zone.HAND,
        energy_type=etype,
        attach_directly=attach,
        filter_text=raw,
        raw_text=raw,
    )


SEARCH_RULES: list[Rule] = [
    Rule(
        "search_deck_up_to_n",
        _compile(
            r"[Ss]earch your deck for " + UP_TO_N + r" (?P<ctype>[^,.]+?)"
            r"(?:, reveal (?:it|them))?,? and put (?:it|them) (?:into your hand|onto your Bench)"
        ),
        _search_deck,
        priority=50,
    ),
    Rule(
        "search_deck_a_card",
        _compile(
            r"[Ss]earch your deck for (?:a|an) (?:Basic )?(?P<etype>" + ENERGY_TYPE + r" )?"
            r"(?P<ctype>[A-Za-z é{}\[\]']+?) card"
        ),
        _search_deck,
        priority=51,
    ),
    Rule(
        "search_deck_any_number",
        _compile(
            r"[Ss]earch your deck for any number of (?P<ctype>[^,.]+?) and put (?:it|them)"
        ),
        lambda m, raw: M.SearchDeck(
            card_type=m.group("ctype").strip(), count=None,
            destination=Zone.BENCH if "Bench" in raw else Zone.HAND,
            filter_text=raw, raw_text=raw,
        ),
        priority=52,
    ),
    Rule(
        "search_deck_evolve",
        _compile(
            r"[Ss]earch your deck for a card that evolves from"
        ),
        lambda m, raw: M.SearchDeck(
            card_type="Evolution Pokemon", count=1, destination=Zone.PLAY,
            filter_text=raw, raw_text=raw,
        ),
        priority=53,
    ),
]

# ---- Attach energy --------------------------------------------------------

def _attach_energy(m: re.Match, raw: str) -> M.AttachEnergy:
    groups = m.groupdict()
    count_raw = groups.get("count") or groups.get("n") or "1"
    count = _int(count_raw, 1)
    etype = _energy_type(groups.get("etype"))
    source = Zone.DISCARD if "discard" in raw.lower() else Zone.HAND
    target_str = raw.lower()
    if "bench" in target_str:
        tgt = Target.BENCHED_SELF
    elif "this pokémon" in target_str or "this pokemon" in target_str:
        tgt = Target.SELF
    elif "your pokémon" in target_str or "your pokemon" in target_str:
        tgt = Target.ANY_SELF
    else:
        tgt = Target.ANY_SELF
    return M.AttachEnergy(
        source=source, target=tgt, count=count, energy_type=etype,
        target_filter=raw[:80], raw_text=raw,
    )


ATTACH_RULES: list[Rule] = [
    Rule(
        "attach_basic_energy",
        _compile(
            r"[Aa]ttach (?:" + UP_TO_N + r"|(?P<n>" + NUM_WORD + r"))? ?"
            r"Basic (?P<etype>" + ENERGY_TYPE + r" )?Energy cards?"
        ),
        _attach_energy,
        priority=60,
    ),
    Rule(
        "attach_any_energy_hand",
        _compile(r"[Aa]ttach (?:an? )?Energy card from your hand to"),
        lambda m, raw: M.AttachEnergy(source=Zone.HAND, target=Target.ANY_SELF, raw_text=raw),
        priority=61,
    ),
    Rule(
        "attach_energy_discard",
        _compile(r"[Aa]ttach (?:an? )?Energy card from your discard pile to"),
        lambda m, raw: M.AttachEnergy(source=Zone.DISCARD, target=Target.ANY_SELF, raw_text=raw),
        priority=62,
    ),
]

# ---- Move energy ----------------------------------------------------------

MOVE_ENERGY_RULES: list[Rule] = [
    Rule(
        "move_energy_bench",
        _compile(r"[Mm]ove (?P<n>" + NUM_WORD + r"|all|an?)? ?(?P<etype>" + ENERGY_TYPE + r" )?Energy from"),
        lambda m, raw: M.MoveEnergy(
            count=None if (m.groupdict().get("n") or "").lower() == "all" else _int(m.groupdict().get("n"), 1),
            energy_type=_energy_type(m.groupdict().get("etype")),
            raw_text=raw,
        ),
        priority=70,
    ),
]

# ---- Damage modifier ------------------------------------------------------

def _dmg_mod(m: re.Match, raw: str) -> M.DamageModifier:
    n = _int(m.group("n"), 0)
    more = "more" in raw.lower()
    less = "less" in raw.lower()
    delta = n if more else (-n if less else n)
    return M.DamageModifier(
        delta=delta,
        condition_text=raw[:120],
        raw_text=raw,
    )


DAMAGE_MOD_RULES: list[Rule] = [
    Rule(
        "dmg_more",
        _compile(r"this attack does (?P<n>" + NUM_DIGIT + r") more damage"),
        _dmg_mod,
        priority=80,
    ),
    Rule(
        "dmg_less_attack",
        _compile(r"attacks.*?do (?P<n>" + NUM_DIGIT + r") (?:more|less) damage"),
        _dmg_mod,
        priority=81,
    ),
    Rule(
        "this_pokemon_takes_less",
        _compile(r"this Pok[eé]mon takes (?P<n>" + NUM_DIGIT + r") less damage from attacks"),
        lambda m, raw: M.PreventDamage(
            target=Target.SELF, max_damage=None,
            all_damage=False, raw_text=raw,
        ),
        priority=82,
    ),
]

# ---- Bench damage ---------------------------------------------------------

def _bench_dmg(m: re.Match, raw: str) -> M.BenchDamage:
    n = _int(m.group("n"), 0)
    tl = raw.lower()
    if "your bench" in tl or "your benched" in tl:
        tgt = Target.BENCHED_SELF
    else:
        tgt = Target.BENCHED_OPP
    count_match = re.search(r"(\d+) of your opponent", raw)
    count = int(count_match.group(1)) if count_match else None
    return M.BenchDamage(amount=n, target=tgt, count=count, raw_text=raw)


BENCH_DAMAGE_RULES: list[Rule] = [
    Rule(
        "bench_dmg_opp",
        _compile(
            r"(?:also )?does (?P<n>" + NUM_DIGIT + r") damage to "
            r"(?:\d+ of )?your opponent['']s Benched Pok[eé]mon"
        ),
        _bench_dmg,
        priority=90,
    ),
    Rule(
        "bench_dmg_each",
        _compile(
            r"(?:also )?does (?P<n>" + NUM_DIGIT + r") damage to each "
            r"(?:Benched|of your Benched|of your opponent['']s Benched) Pok[eé]mon"
        ),
        _bench_dmg,
        priority=91,
    ),
    Rule(
        "bench_dmg_self",
        _compile(
            r"(?:also )?does (?P<n>" + NUM_DIGIT + r") damage to "
            r"(?:1 of )?your Benched Pok[eé]mon"
        ),
        lambda m, raw: M.BenchDamage(amount=_int(m.group("n")), target=Target.BENCHED_SELF, raw_text=raw),
        priority=92,
    ),
]

# ---- Self damage (recoil) -------------------------------------------------

SELF_DAMAGE_RULES: list[Rule] = [
    Rule(
        "self_dmg_also",
        _compile(r"[Tt]his Pok[eé]mon also does (?P<n>" + NUM_DIGIT + r") damage to itself"),
        lambda m, raw: M.SelfDamage(amount=_int(m.group("n")), raw_text=raw),
        priority=100,
    ),
    Rule(
        "self_dmg_does",
        _compile(r"[Tt]his Pok[eé]mon does (?P<n>" + NUM_DIGIT + r") damage to itself"),
        lambda m, raw: M.SelfDamage(amount=_int(m.group("n")), raw_text=raw),
        priority=101,
    ),
]

# ---- Damage counters (not damage) -----------------------------------------

DAMAGE_COUNTER_RULES: list[Rule] = [
    Rule(
        "place_n_counters",
        _compile(
            r"[Pp]lace (?P<n>" + NUM_DIGIT + r") damage counters? on "
            r"(?:1 of )?your opponent['']s"
        ),
        lambda m, raw: M.DamageCounters(
            count=_int(m.group("n")), target=Target.ACTIVE_OPP, raw_text=raw
        ),
        priority=110,
    ),
    Rule(
        "place_counters_bench",
        _compile(r"[Pp]lace (?P<n>" + NUM_DIGIT + r") damage counters? on your opponent['']s Benched"),
        lambda m, raw: M.DamageCounters(
            count=_int(m.group("n")), target=Target.BENCHED_OPP, raw_text=raw
        ),
        priority=111,
    ),
    Rule(
        "put_n_counters",
        _compile(r"[Pp]ut (?P<n>" + NUM_DIGIT + r") damage counters? on"),
        lambda m, raw: M.DamageCounters(
            count=_int(m.group("n")), target=Target.ACTIVE_OPP, raw_text=raw
        ),
        priority=112,
    ),
]

# ---- Variable damage (for each X) ----------------------------------------

def _var_dmg(m: re.Match, raw: str) -> M.VariableDamage:
    n = _int(m.group("n"), 0)
    scale_text = m.groupdict().get("scale", "unknown").strip()
    return M.VariableDamage(
        base_per_unit=n,
        scale_by=scale_text,
        raw_text=raw,
    )


VAR_DAMAGE_RULES: list[Rule] = [
    Rule(
        "var_dmg_for_each_heads",
        _compile(r"[Tt]his attack does (?P<n>" + NUM_DIGIT + r") (?:more )?damage for each heads"),
        lambda m, raw: M.VariableDamage(
            base_per_unit=_int(m.group("n")), scale_by="heads", raw_text=raw
        ),
        priority=120,
    ),
    Rule(
        "var_dmg_for_each",
        _compile(
            r"[Tt]his attack does (?P<n>" + NUM_DIGIT + r") (?:more )?damage for each "
            r"(?P<scale>[^.(]+)"
        ),
        _var_dmg,
        priority=121,
    ),
    Rule(
        "var_dmg_20_per_damage_counter",
        _compile(r"[Tt]his attack does (?P<n>" + NUM_DIGIT + r") damage for each damage counter on"),
        lambda m, raw: M.VariableDamage(
            base_per_unit=_int(m.group("n")), scale_by="damage_counter_on_target", raw_text=raw
        ),
        priority=122,
    ),
]

# ---- Coin flip ------------------------------------------------------------

def _coin_flip_heads_dmg_more(m: re.Match, raw: str) -> M.CoinFlip:
    n = _int(m.group("n"), 0)
    return M.CoinFlip(
        num_coins=1,
        outcomes=(
            M.CoinFlipOutcome(
                result="heads",
                effect=M.DamageModifier(delta=n, raw_text=raw),
            ),
        ),
        raw_text=raw,
    )


def _coin_flip_n_for_heads(m: re.Match, raw: str) -> M.CoinFlip:
    num_coins = _int(m.groupdict().get("coins", "1"), 1)
    dmg = _int(m.group("n"), 0)
    return M.CoinFlip(
        num_coins=num_coins,
        per_heads_effect=M.VariableDamage(base_per_unit=dmg, scale_by="heads", raw_text=raw),
        outcomes=(),
        raw_text=raw,
    )


def _coin_flip_until_tails(m: re.Match, raw: str) -> M.CoinFlip:
    dmg = _int(m.group("n"), 0)
    return M.CoinFlip(
        num_coins=1,
        until_tails=True,
        per_heads_effect=M.VariableDamage(base_per_unit=dmg, scale_by="heads", raw_text=raw),
        outcomes=(),
        raw_text=raw,
    )


COIN_FLIP_RULES: list[Rule] = [
    # Coin-flip combined rules must fire BEFORE the generic dmg_more rule (priority 80),
    # because they are more specific (they anchor on the "Flip a coin" prefix).
    Rule(
        "flip_heads_dmg_more",
        _compile(
            r"[Ff]lip a coin\. If heads, this attack does (?P<n>" + NUM_DIGIT + r") more damage"
        ),
        _coin_flip_heads_dmg_more,
        priority=70,
    ),
    Rule(
        "flip_n_coins_dmg_per_heads",
        _compile(
            r"[Ff]lip (?P<coins>" + NUM_WORD + r") coins?\. "
            r"[Tt]his attack does (?P<n>" + NUM_DIGIT + r") (?:more )?damage for each heads"
        ),
        _coin_flip_n_for_heads,
        priority=71,
    ),
    Rule(
        "flip_until_tails_dmg",
        _compile(
            r"[Ff]lip a coin until you get tails\. "
            r"[Tt]his attack does (?P<n>" + NUM_DIGIT + r") (?:more )?damage for each heads"
        ),
        _coin_flip_until_tails,
        priority=72,
    ),
    Rule(
        "flip_heads_status",
        _compile(
            r"[Ff]lip a coin\. If heads, your opponent['']s Active Pok[eé]mon is now "
            r"(?P<sc>" + STATUS_NAME + r")"
        ),
        lambda m, raw: M.CoinFlip(
            num_coins=1,
            outcomes=(
                M.CoinFlipOutcome(
                    result="heads",
                    effect=M.StatusConditionEffect(
                        condition=_status(m.group("sc")), target=Target.ACTIVE_OPP, raw_text=raw
                    ),
                ),
            ),
            raw_text=raw,
        ),
        priority=73,
    ),
    Rule(
        "flip_coin_if_tails_nothing",
        _compile(r"[Ff]lip a coin\. If tails, this attack does nothing"),
        lambda m, raw: M.CoinFlip(
            num_coins=1,
            outcomes=(
                M.CoinFlipOutcome(result="tails", effect=M.UnknownEffect(text="attack does nothing", raw_text=raw)),
            ),
            raw_text=raw,
        ),
        priority=74,
    ),
    Rule(
        "flip_a_coin_energy_per",
        _compile(r"[Ff]lip a coin for each (?P<scale>[^.]+?)\."),
        lambda m, raw: M.CoinFlip(
            num_coins=1,
            per_heads_effect=M.VariableDamage(base_per_unit=0, scale_by=m.group("scale").strip(), raw_text=raw),
            outcomes=(),
            raw_text=raw,
        ),
        priority=75,
    ),
]

# ---- Switch active --------------------------------------------------------

SWITCH_RULES: list[Rule] = [
    Rule(
        "switch_own_active",
        _compile(r"[Ss]witch your Active Pok[eé]mon with 1 of your Benched Pok[eé]mon"),
        lambda m, raw: M.SwitchActive(who=Target.ACTIVE_SELF, raw_text=raw),
        priority=140,
    ),
    Rule(
        "switch_self_pokemon",
        _compile(r"[Ss]witch this Pok[eé]mon with 1 of your Benched Pok[eé]mon"),
        lambda m, raw: M.SwitchActive(who=Target.SELF, raw_text=raw),
        priority=141,
    ),
    Rule(
        "force_switch_in_bench",
        _compile(r"[Ss]witch in 1 of your opponent['']s Benched Pok[eé]mon to the Active Spot"),
        lambda m, raw: M.ForceSwitch(from_bench=True, opponent_chooses=False, raw_text=raw),
        priority=142,
    ),
    Rule(
        "force_switch_out",
        _compile(r"[Ss]witch out your opponent['']s Active Pok[eé]mon to the Bench"),
        lambda m, raw: M.ForceSwitch(from_bench=False, opponent_chooses=True, raw_text=raw),
        priority=143,
    ),
]

# ---- Prevent damage -------------------------------------------------------

PREVENT_RULES: list[Rule] = [
    Rule(
        "prevent_all_dmg_self",
        _compile(r"[Pp]revent all damage done to this Pok[eé]mon by attacks"),
        lambda m, raw: M.PreventDamage(target=Target.SELF, all_damage=True, raw_text=raw),
        priority=150,
    ),
    Rule(
        "prevent_all_dmg_bench",
        _compile(r"[Pp]revent all damage (?:from and effects of )?attacks? from your opponent['']s Pok[eé]mon done to your Benched"),
        lambda m, raw: M.PreventDamage(target=Target.BENCHED_SELF, all_damage=True, raw_text=raw),
        priority=151,
    ),
    Rule(
        "prevent_dmg_threshold",
        _compile(
            r"[Pp]revent all damage done to this Pok[eé]mon by attacks if that damage is "
            r"(?P<n>" + NUM_DIGIT + r") or less"
        ),
        lambda m, raw: M.PreventDamage(target=Target.SELF, max_damage=_int(m.group("n")), raw_text=raw),
        priority=152,
    ),
    Rule(
        "prevent_effects_attacks",
        _compile(r"[Pp]revent all effects of attacks used by your opponent['']s Pok[eé]mon done to"),
        lambda m, raw: M.PreventDamage(
            target=Target.SELF, include_effects=True, all_damage=False, raw_text=raw
        ),
        priority=153,
    ),
]

# ---- KO -------------------------------------------------------------------

KO_RULES: list[Rule] = [
    Rule(
        "ko_direct",
        _compile(r"[Kk]nock [Oo]ut (?:your opponent['']s Active|1 of your opponent['']s) (?:Basic )?Pok[eé]mon"),
        lambda m, raw: M.KnockOut(target=Target.ACTIVE_OPP, raw_text=raw),
        priority=160,
    ),
    Rule(
        "ko_both",
        _compile(r"[Bb]oth Active Pok[eé]mon are Knocked Out"),
        lambda m, raw: M.KnockOut(target=Target.BOTH_ACTIVE, raw_text=raw),
        priority=161,
    ),
    Rule(
        "ko_if_condition",
        _compile(r"(?:it is|they are|that Pok[eé]mon is) Knocked Out"),
        lambda m, raw: M.KnockOut(target=Target.ACTIVE_OPP, raw_text=raw),
        priority=162,
    ),
]

# ---- Shuffle --------------------------------------------------------------

SHUFFLE_RULES: list[Rule] = [
    Rule(
        "shuffle_hand_draw",
        _compile(
            r"[Ss]huffle your hand into your deck[.,]?\s*[Tt]hen[,.]?\s*draw (?P<n>" + NUM_DIGIT + r") cards?"
        ),
        lambda m, raw: M.ShuffleEffect(hand_first=True, draw_after=_int(m.group("n")), raw_text=raw),
        priority=170,
    ),
    Rule(
        "shuffle_deck",
        _compile(r"[Ss]huffle your deck"),
        lambda m, raw: M.ShuffleEffect(hand_first=False, raw_text=raw),
        priority=171,
    ),
    Rule(
        "shuffle_opp_deck",
        _compile(r"[Ss]huffle (?:their|your opponent['']s) (?:deck|hand)"),
        lambda m, raw: M.ShuffleEffect(who=Target.ACTIVE_OPP, raw_text=raw),
        priority=172,
    ),
]

# ---- Mill -----------------------------------------------------------------

MILL_RULES: list[Rule] = [
    Rule(
        "mill_self_top_n",
        _compile(r"discard the top (?P<n>" + NUM_DIGIT + r") cards? of your deck"),
        lambda m, raw: M.MillEffect(count=_int(m.group("n")), who=Target.ACTIVE_SELF, raw_text=raw),
        priority=180,
    ),
]

# ---- Prize ----------------------------------------------------------------

PRIZE_RULES: list[Rule] = [
    Rule(
        "take_prize_card",
        _compile(r"take (?:a|1|one) (?:more )?Prize cards?"),
        lambda m, raw: M.PrizeEffect(take=1, raw_text=raw),
        priority=190,
    ),
    Rule(
        "look_prize",
        _compile(r"[Ll]ook at (?:1 of|a) your (?:face-down )?Prize cards?"),
        lambda m, raw: M.PrizeEffect(take=0, look=True, raw_text=raw),
        priority=191,
    ),
]

# ---- Evolve / Devolve -----------------------------------------------------

EVOLVE_RULES: list[Rule] = [
    Rule(
        "evolve_pokemon",
        _compile(r"evolve (?:it|1 of your Pok[eé]mon|this Pok[eé]mon)"),
        lambda m, raw: M.EvolveEffect(raw_text=raw),
        priority=200,
    ),
    Rule(
        "devolve_opp",
        _compile(r"[Dd]evolve (?:1 of )?your opponent['']s evolved Pok[eé]mon"),
        lambda m, raw: M.DevolveEffect(target=Target.ANY_OPP, raw_text=raw),
        priority=201,
    ),
]

# ---- Passive / Ability wrappers -------------------------------------------

PASSIVE_RULES: list[Rule] = [
    Rule(
        "once_during_turn_ability",
        _compile(r"[Oo]nce during your turn(?:, [^,]+)?, you may"),
        lambda m, raw: M.PassiveEffect(
            frequency=Frequency.ONCE_PER_TURN,
            trigger="",
            description=raw[:120],
            raw_text=raw,
        ),
        priority=210,
    ),
    Rule(
        "as_often_as_like",
        _compile(r"[Aa]s often as you like during your turn"),
        lambda m, raw: M.PassiveEffect(
            frequency=Frequency.AS_OFTEN_AS_LIKE,
            description=raw[:120],
            raw_text=raw,
        ),
        priority=211,
    ),
    Rule(
        "as_long_as_passive",
        _compile(r"[Aa]s long as this (?:Pok[eé]mon|card)"),
        lambda m, raw: M.PassiveEffect(
            frequency=Frequency.PASSIVE,
            description=raw[:120],
            raw_text=raw,
        ),
        priority=212,
    ),
]

# ---- Retreat cost ---------------------------------------------------------

RETREAT_RULES: list[Rule] = [
    Rule(
        "no_retreat",
        _compile(r"(?:has no|have no) Retreat Cost"),
        lambda m, raw: M.RetreatCostEffect(delta=-99, target=Target.SELF, raw_text=raw),
        priority=220,
    ),
    Rule(
        "retreat_less",
        _compile(r"Retreat Cost.*?is (?P<e>" + ENERGY_TYPE + r"){1,2} less"),
        lambda m, raw: M.RetreatCostEffect(delta=-1, target=Target.SELF, raw_text=raw),
        priority=221,
    ),
    Rule(
        "retreat_more",
        _compile(r"Retreat Cost.*?is (?P<e>" + ENERGY_TYPE + r"){1,2} more"),
        lambda m, raw: M.RetreatCostEffect(delta=1, target=Target.ANY_OPP, raw_text=raw),
        priority=222,
    ),
]

# ---- Return to hand -------------------------------------------------------

RETURN_HAND_RULES: list[Rule] = [
    Rule(
        "put_bench_into_hand",
        _compile(r"[Pp]ut (?:1 of )?your Benched Pok[eé]mon and all attached cards into your hand"),
        lambda m, raw: M.ReturnToHand(target=Target.BENCHED_SELF, include_attached=True, raw_text=raw),
        priority=230,
    ),
    Rule(
        "put_this_into_hand",
        _compile(r"[Pp]ut this Pok[eé]mon and all attached cards into your hand"),
        lambda m, raw: M.ReturnToHand(target=Target.SELF, include_attached=True, raw_text=raw),
        priority=231,
    ),
    Rule(
        "return_from_discard",
        _compile(r"[Pp]ut (?:up to (?P<n>\d+) )?(?P<ctype>Pok[eé]mon|Energy|Trainer|Supporter|Basic Energy) (?:cards? )?from your discard pile into your hand"),
        lambda m, raw: M.SearchDiscard(
            card_type=m.group("ctype"),
            count=_int(m.groupdict().get("n", "1")),
            destination=Zone.HAND,
            raw_text=raw,
        ),
        priority=232,
    ),
]

# ---- Ability suppression --------------------------------------------------

SUPPRESS_RULES: list[Rule] = [
    Rule(
        "ability_suppression",
        _compile(r"(?:have no|has no) Abilit(?:y|ies)(?:, except)?"),
        lambda m, raw: M.AbilitySuppression(
            target=Target.ANY_OPP, raw_text=raw
        ),
        priority=240,
    ),
]

# ---- Copy attack ----------------------------------------------------------

COPY_RULES: list[Rule] = [
    Rule(
        "copy_opp_attack",
        _compile(r"[Cc]hoose 1 of your opponent['']s (?:Active )?Pok[eé]mon['']s attacks? and use it"),
        lambda m, raw: M.CopyAttack(copy_from="opponent_active", raw_text=raw),
        priority=250,
    ),
]

# ---- Tool interaction -----------------------------------------------------

TOOL_RULES: list[Rule] = [
    Rule(
        "tool_attached_modifier",
        _compile(r"[Pp]ok[eé]mon Tools? attached"),
        lambda m, raw: M.ToolInteraction(operation="check_attached", target=Target.ANY_SELF, raw_text=raw),
        priority=260,
    ),
]

# ---- Stadium interaction --------------------------------------------------

STADIUM_RULES: list[Rule] = [
    Rule(
        "stadium_in_play_check",
        _compile(r"[Ss]tadium is in play"),
        lambda m, raw: M.StadiumInteraction(operation="check_in_play", raw_text=raw),
        priority=270,
    ),
]

# ---- All rules in priority order ------------------------------------------

ALL_RULES: list[Rule] = sorted(
    DRAW_RULES
    + HEAL_RULES
    + STATUS_RULES
    + DISCARD_RULES
    + SEARCH_RULES
    + ATTACH_RULES
    + MOVE_ENERGY_RULES
    + DAMAGE_MOD_RULES
    + BENCH_DAMAGE_RULES
    + SELF_DAMAGE_RULES
    + DAMAGE_COUNTER_RULES
    + VAR_DAMAGE_RULES
    + COIN_FLIP_RULES
    + SWITCH_RULES
    + PREVENT_RULES
    + KO_RULES
    + SHUFFLE_RULES
    + MILL_RULES
    + PRIZE_RULES
    + EVOLVE_RULES
    + PASSIVE_RULES
    + RETREAT_RULES
    + RETURN_HAND_RULES
    + SUPPRESS_RULES
    + COPY_RULES
    + TOOL_RULES
    + STADIUM_RULES,
    key=lambda r: r.priority,
)
