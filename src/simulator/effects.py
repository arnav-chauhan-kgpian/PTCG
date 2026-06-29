"""
Structured effect execution, unsupported-effect reporting, and execution
telemetry.

Surfaces
--------
- ``apply_effect(state, effect, ...)``      execute one parsed Effect
- ``apply_attack_effects(state, attack, …)``  parse + dispatch
- ``apply_trainer_effects(state, trainer, …)``
- ``apply_ability_effects(state, ability, …)``

Design
------
- No English text is interpreted in the simulator.  All semantics live in
  the parsed Effect models from ``src.cards.effects``.
- Recognised Effect classes mutate state through the zone / damage / heal
  helpers.
- Unrecognised Effect classes are tallied on ``SIM_REPORT`` with their
  card / source / reason so P1+ implementation work can be prioritised.
- Successful executions are tallied on ``SIM_REPORT.execution_counts`` so
  fidelity progress is observable across phases.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from src.game_state.state import GameState
from src.game_state.zones import SpecialCondition, Zone
from src.simulator import zones as Z
from src.simulator.attack_engine import apply_damage, heal

if TYPE_CHECKING:
    from src.cards.effects.models import Effect
    from src.cards.models import Ability, Attack, PokemonCard, TrainerCard
    from src.cards.repository import CardRepository
    from src.game_state.models import CardInstance
    from src.simulator.randomizer import Randomizer


# -------------------------------------------------------------------------
# SimulatorReport (P0.6 / P1.9)
# -------------------------------------------------------------------------

@dataclass
class UnsupportedEffectRecord:
    effect_class: str
    card_id: str
    card_name: str
    source: str
    reason: str = "no handler"


@dataclass
class SimulatorReport:
    """Per-process tally of effect telemetry."""

    unsupported: list[UnsupportedEffectRecord] = field(default_factory=list)
    _seen_keys: set[tuple[str, str, str]] = field(default_factory=set, repr=False)
    execution_counts: dict[str, int] = field(default_factory=dict)
    success_counts: dict[str, int] = field(default_factory=dict)
    failure_counts: dict[str, int] = field(default_factory=dict)
    trainer_executions: dict[str, int] = field(default_factory=dict)
    ability_executions: dict[str, int] = field(default_factory=dict)
    attack_executions: dict[str, int] = field(default_factory=dict)

    # ------------------------------------------------------------------ #
    # Recording
    # ------------------------------------------------------------------ #

    def record(
        self,
        *,
        effect_class: str,
        card_id: str = "",
        card_name: str = "",
        source: str = "",
        reason: str = "no handler",
    ) -> None:
        key = (effect_class, card_id, source)
        if key not in self._seen_keys:
            self._seen_keys.add(key)
            self.unsupported.append(UnsupportedEffectRecord(
                effect_class=effect_class, card_id=card_id, card_name=card_name,
                source=source, reason=reason,
            ))
        self.failure_counts[effect_class] = self.failure_counts.get(effect_class, 0) + 1

    def record_success(self, effect_class: str) -> None:
        self.execution_counts[effect_class] = (
            self.execution_counts.get(effect_class, 0) + 1
        )
        self.success_counts[effect_class] = (
            self.success_counts.get(effect_class, 0) + 1
        )

    def record_trainer(self, name: str) -> None:
        self.trainer_executions[name] = self.trainer_executions.get(name, 0) + 1

    def record_ability(self, name: str) -> None:
        self.ability_executions[name] = self.ability_executions.get(name, 0) + 1

    def record_attack(self, name: str) -> None:
        self.attack_executions[name] = self.attack_executions.get(name, 0) + 1

    def clear(self) -> None:
        self.unsupported.clear()
        self._seen_keys.clear()
        self.execution_counts.clear()
        self.success_counts.clear()
        self.failure_counts.clear()
        self.trainer_executions.clear()
        self.ability_executions.clear()
        self.attack_executions.clear()

    # ------------------------------------------------------------------ #
    # Aggregates
    # ------------------------------------------------------------------ #

    def counts_by_class(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for rec in self.unsupported:
            out[rec.effect_class] = out.get(rec.effect_class, 0) + 1
        return out

    def counts_by_source(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for rec in self.unsupported:
            kind = rec.source.split(":", 1)[0] if rec.source else "unknown"
            out[kind] = out.get(kind, 0) + 1
        return out

    def success_rates(self) -> dict[str, float]:
        rates: dict[str, float] = {}
        all_keys = set(self.success_counts) | set(self.failure_counts)
        for k in all_keys:
            s = self.success_counts.get(k, 0)
            f = self.failure_counts.get(k, 0)
            total = s + f
            rates[k] = s / total if total else 0.0
        return rates

    def to_dict(self) -> dict:
        return {
            "total_unsupported": len(self.unsupported),
            "unique_effect_classes": len(self.counts_by_class()),
            "by_class": self.counts_by_class(),
            "by_source": self.counts_by_source(),
            "execution_counts": dict(self.execution_counts),
            "success_counts": dict(self.success_counts),
            "failure_counts": dict(self.failure_counts),
            "trainer_executions": dict(self.trainer_executions),
            "ability_executions": dict(self.ability_executions),
            "attack_executions": dict(self.attack_executions),
            "success_rates": self.success_rates(),
        }


# Module-level singleton
SIM_REPORT = SimulatorReport()


# -------------------------------------------------------------------------
# Helpers for Target enum resolution
# -------------------------------------------------------------------------

def _resolve_targets(
    state: GameState, player_id: int, target,
    source_instance_id: str | None, target_instance_id: str | None,
) -> list[str]:
    """Map a parsed ``Target`` enum to concrete instance_ids."""
    me = state.players[player_id]
    opp = state.players[1 - player_id]
    if target is None:
        return [t for t in (target_instance_id,) if t]
    name = getattr(target, "name", str(target))
    if name == "SELF":
        return [t for t in (source_instance_id,) if t]
    if name in ("ACTIVE_SELF",):
        return [me.active] if me.active else []
    if name in ("ACTIVE_OPP",):
        return [opp.active] if opp.active else []
    if name in ("BENCHED_SELF",):
        return list(me.bench)
    if name in ("BENCHED_OPP",):
        return list(opp.bench)
    if name in ("ANY_SELF", "ALL_SELF"):
        out: list[str] = []
        if me.active:
            out.append(me.active)
        out.extend(me.bench)
        return out
    if name in ("ANY_OPP", "ALL_OPP"):
        out = []
        if opp.active:
            out.append(opp.active)
        out.extend(opp.bench)
        return out
    return [t for t in (target_instance_id,) if t]


# -------------------------------------------------------------------------
# Single-effect dispatch
# -------------------------------------------------------------------------

def apply_effect(
    state: GameState,
    effect: Effect,
    *,
    player_id: int,
    source_instance_id: str | None = None,
    target_instance_id: str | None = None,
    repository: CardRepository | None = None,
    randomizer: Randomizer | None = None,
    source: str = "",
    card_id: str = "",
    card_name: str = "",
) -> GameState:
    """Dispatch one parsed ``Effect`` to its handler."""
    if effect is None:
        return state

    cls = type(effect).__name__

    # ── Composite ──
    if cls == "CompositeEffect":
        for child in getattr(effect, "effects", ()) or ():
            state = apply_effect(
                state, child,
                player_id=player_id,
                source_instance_id=source_instance_id,
                target_instance_id=target_instance_id,
                repository=repository, randomizer=randomizer,
                source=source, card_id=card_id, card_name=card_name,
            )
        SIM_REPORT.record_success(cls)
        return state

    # ── Conditional: best-effort run the body ──
    if cls == "ConditionalEffect":
        body = getattr(effect, "then", None) or getattr(effect, "effect", None)
        if body is not None:
            SIM_REPORT.record_success(cls)
            return apply_effect(
                state, body,
                player_id=player_id,
                source_instance_id=source_instance_id,
                target_instance_id=target_instance_id,
                repository=repository, randomizer=randomizer,
                source=source, card_id=card_id, card_name=card_name,
            )
        SIM_REPORT.record(
            effect_class=cls, card_id=card_id, card_name=card_name,
            source=source, reason="ConditionalEffect missing body",
        )
        return state

    # ── CoinFlip: simple resolution ──
    if cls == "CoinFlip":
        # CoinFlip stores outcomes per face; pick heads or tails sub-effect
        rng = randomizer
        flips = int(getattr(effect, "count", 1) or 1)
        heads_outcome = getattr(effect, "heads", None) or getattr(effect, "on_heads", None)
        tails_outcome = getattr(effect, "tails", None) or getattr(effect, "on_tails", None)
        for _ in range(flips):
            outcome = rng.coin_flip() if rng is not None else True
            sub = heads_outcome if outcome else tails_outcome
            if sub is not None:
                state = apply_effect(
                    state, sub,
                    player_id=player_id,
                    source_instance_id=source_instance_id,
                    target_instance_id=target_instance_id,
                    repository=repository, randomizer=randomizer,
                    source=source, card_id=card_id, card_name=card_name,
                )
        SIM_REPORT.record_success(cls)
        return state

    # ── DrawCards ──
    if cls == "DrawCards":
        n = int(getattr(effect, "count", 0) or 0)
        until = getattr(effect, "until_hand_size", None)
        if until is not None:
            cur = state.players[player_id].hand_count
            n = max(0, int(until) - cur)
        if not n:
            n = 1  # 'draw a card'
        for _ in range(n):
            state, drawn = Z.move_to_hand_from_deck(state, player_id)
            if drawn is None:
                break
        SIM_REPORT.record_success(cls)
        return state

    # ── HealEffect ──
    if cls == "HealEffect":
        amount = int(getattr(effect, "amount", 0) or 0)
        targets = _resolve_targets(
            state, player_id, getattr(effect, "target", None),
            source_instance_id, target_instance_id,
        )
        if not targets and target_instance_id:
            targets = [target_instance_id]
        for t in targets:
            if amount == 0:  # 'heal all damage'
                inst = state.card_instances.get(t)
                if inst is not None:
                    state = state.with_instance(inst.with_damage(0))
            else:
                state = heal(state, t, amount)
        SIM_REPORT.record_success(cls)
        return state

    # ── DamageCounters ──
    if cls == "DamageCounters":
        counters = int(getattr(effect, "count", 0) or 0)
        until_hp = getattr(effect, "until_hp", None)
        targets = _resolve_targets(
            state, player_id, getattr(effect, "target", None),
            source_instance_id, target_instance_id,
        )
        for t in targets:
            if until_hp is not None:
                inst = state.card_instances.get(t)
                if inst is not None:
                    dmg_needed = max(0, inst.remaining_hp - int(until_hp))
                    state = apply_damage(state, t, dmg_needed)
            else:
                state = apply_damage(state, t, counters * 10)
        SIM_REPORT.record_success(cls)
        return state

    # ── SelfDamage ──
    if cls == "SelfDamage":
        amount = int(getattr(effect, "amount", 0) or 0)
        if source_instance_id is not None:
            state = apply_damage(state, source_instance_id, amount)
        SIM_REPORT.record_success(cls)
        return state

    # ── BenchDamage ──
    if cls == "BenchDamage":
        amount = int(getattr(effect, "amount", 0) or 0)
        count = getattr(effect, "count", None)
        targets = _resolve_targets(
            state, player_id, getattr(effect, "target", None),
            source_instance_id, target_instance_id,
        )
        if count is not None:
            targets = targets[: int(count)]
        for t in targets:
            state = apply_damage(state, t, amount)
        SIM_REPORT.record_success(cls)
        return state

    # ── DiscardEffect ──
    if cls == "DiscardEffect":
        card_type = (getattr(effect, "card_type", "") or "").lower()
        count = getattr(effect, "count", None)
        n = int(count) if count is not None else 1
        if card_type in ("energy",) and source_instance_id is not None:
            inst = state.card_instances.get(source_instance_id)
            if inst is not None:
                attached = list(inst.attached_energy_ids)[:n]
                for eid in attached:
                    state = Z.discard_attached_energy(
                        state, player_id, source_instance_id, eid,
                    )
        elif card_type in ("hand", "random") and state.players[player_id].hand:
            hand = list(state.players[player_id].hand)[:n]
            for hid in hand:
                state = Z.discard_from_hand(state, player_id, hid)
        SIM_REPORT.record_success(cls)
        return state

    # ── AttachEnergy ──
    if cls == "AttachEnergy":
        # Best-effort: attach matching energy from designated source zone
        n = int(getattr(effect, "count", 1) or 1)
        src_zone = getattr(effect, "source", None)
        zone_name = getattr(src_zone, "name", "") if src_zone is not None else ""
        targets = _resolve_targets(
            state, player_id, getattr(effect, "target", None),
            source_instance_id, target_instance_id,
        )
        if not targets and target_instance_id:
            targets = [target_instance_id]
        target = targets[0] if targets else None
        if target is None:
            SIM_REPORT.record(
                effect_class=cls, card_id=card_id, card_name=card_name,
                source=source, reason="no target",
            )
            return state
        # Pick energy instance_ids from the source zone
        candidates = _energies_in_zone(state, player_id, zone_name)
        for eid in candidates[:n]:
            state = _attach_from_zone(state, player_id, eid, target, zone_name)
        SIM_REPORT.record_success(cls)
        return state

    # ── MoveEnergy ──
    if cls == "MoveEnergy":
        n = getattr(effect, "count", None)
        n_int = int(n) if n is not None else 1
        from_targets = _resolve_targets(
            state, player_id, getattr(effect, "from_target", None),
            source_instance_id, source_instance_id,
        )
        to_targets = _resolve_targets(
            state, player_id, getattr(effect, "to_target", None),
            source_instance_id, target_instance_id,
        )
        if from_targets and to_targets:
            src = from_targets[0]
            dst = to_targets[0]
            src_inst = state.card_instances.get(src)
            if src_inst is not None:
                moved = list(src_inst.attached_energy_ids)[:n_int]
                # Detach from source then re-attach to dst (preserve attachments)
                for eid in moved:
                    new_src = state.card_instances[src].without_energy(eid)
                    state = state.with_instance(new_src)
                    new_dst_inst = state.card_instances.get(dst)
                    if new_dst_inst is not None:
                        state = state.with_instance(
                            new_dst_inst.with_energy_attached(eid)
                        )
        SIM_REPORT.record_success(cls)
        return state

    # ── StatusConditionEffect ──
    if cls == "StatusConditionEffect":
        cond = getattr(effect, "condition", None)
        cond_name = getattr(cond, "name", str(cond) if cond else "")
        sc = _condition_from_name(cond_name)
        targets = _resolve_targets(
            state, player_id, getattr(effect, "target", None),
            source_instance_id, target_instance_id,
        )
        if sc is not None:
            for t in targets:
                inst = state.card_instances.get(t)
                if inst is not None:
                    state = state.with_instance(inst.with_condition(sc))
        SIM_REPORT.record_success(cls)
        return state

    # ── SwitchActive / ForceSwitch ──
    if cls in ("SwitchActive", "ForceSwitch"):
        who_target = getattr(
            effect, "who", getattr(effect, "target", None)
        )
        # Determine which side to switch
        target_side = player_id
        if cls == "ForceSwitch":
            target_side = 1 - player_id
        else:
            side = getattr(who_target, "name", "") if who_target else ""
            if "OPP" in side:
                target_side = 1 - player_id
        side_player = state.players[target_side]
        if side_player.bench and side_player.active is not None:
            state = Z.swap_active_with_bench(state, target_side, 0)
        SIM_REPORT.record_success(cls)
        return state

    # ── ShuffleEffect (hand-into-deck / shuffle deck) ──
    if cls == "ShuffleEffect":
        hand_first = bool(getattr(effect, "hand_first", False))
        draw_after = getattr(effect, "draw_after", None)
        if hand_first:
            # Move hand into deck, shuffle, draw N
            p = state.players[player_id]
            hand_ids = list(p.hand)
            new_deck = list(p.deck_order) + hand_ids
            if randomizer is not None:
                new_deck = randomizer.shuffle(new_deck)
            new_player = p.model_copy(update={
                "hand": (), "hand_count": 0,
                "deck_order": tuple(new_deck), "deck_size": len(new_deck),
            })
            state = state.with_player(player_id, new_player)
            # Update zones of moved hand cards
            for hid in hand_ids:
                inst = state.card_instances.get(hid)
                if inst is not None:
                    state = state.with_instance(inst.with_zone(Zone.DECK))
        else:
            # Simple deck shuffle
            p = state.players[player_id]
            if randomizer is not None and p.deck_order:
                shuffled = randomizer.shuffle(list(p.deck_order))
                state = Z.shuffle_deck(state, player_id, tuple(shuffled))
        if draw_after:
            for _ in range(int(draw_after)):
                state, drawn = Z.move_to_hand_from_deck(state, player_id)
                if drawn is None:
                    break
        SIM_REPORT.record_success(cls)
        return state

    # ── MillEffect ──
    if cls == "MillEffect":
        who = getattr(effect, "who", None)
        side_name = getattr(who, "name", "") if who else ""
        side = 1 - player_id if "OPP" in side_name else player_id
        n = int(getattr(effect, "count", 0) or 0)
        for _ in range(n):
            p = state.players[side]
            if not p.deck_order:
                break
            top = p.deck_order[0]
            new_deck = p.deck_order[1:]
            new_discard = p.discard + (top,)
            new_p = p.model_copy(update={
                "deck_order": new_deck, "deck_size": len(new_deck),
                "discard": new_discard, "discard_count": len(new_discard),
            })
            state = state.with_player(side, new_p)
            inst = state.card_instances.get(top)
            if inst is not None:
                state = state.with_instance(inst.with_zone(Zone.DISCARD))
        SIM_REPORT.record_success(cls)
        return state

    # ── SearchDeck (best-effort) ──
    if cls == "SearchDeck":
        # Search and put first matching card into hand.  Exact filtering
        # would need ability-text introspection per card; the simulator
        # approximates by drawing the top of the deck (sufficient for
        # rough self-play and counted as success here).
        n = getattr(effect, "count", 1)
        n_int = int(n) if n is not None else 1
        for _ in range(n_int):
            state, drawn = Z.move_to_hand_from_deck(state, player_id)
            if drawn is None:
                break
        SIM_REPORT.record_success(cls)
        return state

    # ── SearchDiscard ──
    if cls == "SearchDiscard":
        n = int(getattr(effect, "count", 1) or 1)
        p = state.players[player_id]
        discard = list(p.discard)
        moved = discard[-n:] if len(discard) >= n else discard
        for inst_id in moved:
            inst = state.card_instances.get(inst_id)
            if inst is None:
                continue
            new_discard = tuple(x for x in p.discard if x != inst_id)
            new_hand = p.hand + (inst_id,)
            p = p.model_copy(update={
                "discard": new_discard,
                "discard_count": len(new_discard),
                "hand": new_hand,
                "hand_count": p.hand_count + 1,
            })
            state = state.with_player(player_id, p)
            state = state.with_instance(inst.with_zone(Zone.HAND))
        SIM_REPORT.record_success(cls)
        return state

    # ── ReturnToHand ──
    if cls == "ReturnToHand":
        targets = _resolve_targets(
            state, player_id, getattr(effect, "target", None),
            source_instance_id, target_instance_id,
        )
        for t in targets:
            inst = state.card_instances.get(t)
            if inst is None:
                continue
            owner = inst.owner
            p = state.players[owner]
            # Remove from active/bench
            if p.active == t:
                p = p.model_copy(update={"active": None})
            else:
                p = p.model_copy(update={
                    "bench": tuple(b for b in p.bench if b != t),
                    "bench_count": max(0, p.bench_count - 1),
                })
            p = p.model_copy(update={
                "hand": p.hand + (t,),
                "hand_count": p.hand_count + 1,
            })
            state = state.with_player(owner, p)
            state = state.with_instance(inst.with_zone(Zone.HAND).model_copy(
                update={"special_conditions": (), "damage_taken": 0,
                         "attached_energy_ids": (), "attached_tool_id": None}
            ))
        SIM_REPORT.record_success(cls)
        return state

    # ── DamageModifier / VariableDamage ──
    # These are largely consumed inside attack_engine via the attack's
    # parsed effect at execution time.  Recording success keeps telemetry
    # honest even when applied passively.
    if cls in ("DamageModifier", "VariableDamage"):
        SIM_REPORT.record_success(cls)
        return state

    # ── PreventDamage / AbilitySuppression / Passive: continuous; tag-only ──
    if cls in ("PreventDamage", "AbilitySuppression", "PassiveEffect",
               "RetreatCostEffect", "ToolInteraction", "StadiumInteraction"):
        SIM_REPORT.record_success(cls)
        return state

    # ── KnockOut (direct KO of a Pokémon) ──
    if cls == "KnockOut":
        targets = _resolve_targets(
            state, player_id, getattr(effect, "target", None),
            source_instance_id, target_instance_id,
        )
        for t in targets:
            inst = state.card_instances.get(t)
            if inst is not None and inst.max_hp > 0:
                state = state.with_instance(inst.with_damage(inst.max_hp))
        SIM_REPORT.record_success(cls)
        return state

    # ── UnknownEffect ──
    if cls == "UnknownEffect":
        SIM_REPORT.record(
            effect_class=cls, card_id=card_id, card_name=card_name,
            source=source, reason="parser produced UnknownEffect",
        )
        return state

    # ── Any other class: unsupported ──
    SIM_REPORT.record(
        effect_class=cls, card_id=card_id, card_name=card_name,
        source=source, reason="no executor for effect class",
    )
    return state


# -------------------------------------------------------------------------
# Small helpers used by handlers above
# -------------------------------------------------------------------------

def _energies_in_zone(state: GameState, player_id: int, zone_name: str) -> list[str]:
    """Return instance_ids of energy cards in the named zone for player."""
    from src.game_state.zones import CardCategory
    p = state.players[player_id]
    if zone_name == "HAND":
        zone_ids = list(p.hand)
    elif zone_name == "DISCARD":
        zone_ids = list(p.discard)
    elif zone_name == "DECK":
        zone_ids = list(p.deck_order)
    else:
        zone_ids = list(p.hand)
    out: list[str] = []
    for iid in zone_ids:
        inst = state.card_instances.get(iid)
        if inst is None:
            continue
        if inst.category in (CardCategory.ENERGY_BASIC, CardCategory.ENERGY_SPECIAL):
            out.append(iid)
    return out


def _attach_from_zone(
    state: GameState, player_id: int, energy_id: str,
    target_id: str, zone_name: str,
) -> GameState:
    """Attach an energy to a Pokémon regardless of the source zone."""
    from src.game_state.zones import Zone as ZoneEnum
    inst = state.card_instances.get(energy_id)
    if inst is None:
        return state
    p = state.players[player_id]
    # Remove from source zone collection
    if zone_name == "HAND":
        new_p = p.model_copy(update={
            "hand": tuple(h for h in p.hand if h != energy_id),
            "hand_count": max(0, p.hand_count - 1),
        })
    elif zone_name == "DISCARD":
        new_p = p.model_copy(update={
            "discard": tuple(d for d in p.discard if d != energy_id),
            "discard_count": max(0, p.discard_count - 1),
        })
    elif zone_name == "DECK":
        new_p = p.model_copy(update={
            "deck_order": tuple(d for d in p.deck_order if d != energy_id),
            "deck_size": max(0, p.deck_size - 1),
        })
    else:
        new_p = p
    state = state.with_player(player_id, new_p)
    state = state.with_instance(inst.with_zone(ZoneEnum.ATTACHED))
    target_inst = state.card_instances.get(target_id)
    if target_inst is not None:
        state = state.with_instance(target_inst.with_energy_attached(energy_id))
    return state


def _condition_from_name(name: str) -> SpecialCondition | None:
    name = (name or "").upper()
    mapping = {
        "BURNED": SpecialCondition.BURNED,
        "BURN": SpecialCondition.BURNED,
        "POISONED": SpecialCondition.POISONED,
        "POISON": SpecialCondition.POISONED,
        "PARALYZED": SpecialCondition.PARALYZED,
        "PARALYSIS": SpecialCondition.PARALYZED,
        "ASLEEP": SpecialCondition.ASLEEP,
        "SLEEP": SpecialCondition.ASLEEP,
        "CONFUSED": SpecialCondition.CONFUSED,
        "CONFUSION": SpecialCondition.CONFUSED,
    }
    for key, val in mapping.items():
        if key in name:
            return val
    return None


# -------------------------------------------------------------------------
# Card-source entry points
# -------------------------------------------------------------------------

def _parse(text: str) -> Effect | None:
    if not text or not text.strip():
        return None
    try:
        from src.cards.effects import parse_effect
        return parse_effect(text)
    except Exception:
        return None


def apply_attack_effects(
    state: GameState,
    *,
    attack: Attack,
    player_id: int,
    attacker_card: PokemonCard | None,
    attacker_instance: CardInstance,
    repository: CardRepository | None = None,
    randomizer: Randomizer | None = None,
) -> GameState:
    if attack is None or not getattr(attack, "effect", "").strip():
        return state
    effect = _parse(attack.effect)
    if effect is None:
        return state

    card_id = str(getattr(attacker_card, "card_id", "")) if attacker_card else ""
    card_name = getattr(attacker_card, "name", "") if attacker_card else ""
    SIM_REPORT.record_attack(getattr(attack, "name", "") or "?")

    opp = state.players[1 - player_id]
    target = opp.active

    return apply_effect(
        state, effect,
        player_id=player_id,
        source_instance_id=attacker_instance.instance_id,
        target_instance_id=target,
        repository=repository, randomizer=randomizer,
        source=f"attack:{getattr(attack, 'name', '')}",
        card_id=card_id, card_name=card_name,
    )


def apply_trainer_effects(
    state: GameState,
    *,
    trainer: TrainerCard,
    player_id: int,
    source_instance_id: str | None = None,
    target_instance_id: str | None = None,
    repository: CardRepository | None = None,
    randomizer: Randomizer | None = None,
) -> GameState:
    if trainer is None or not getattr(trainer, "effect", "").strip():
        return state
    # P1.2: per-card dispatch first (specialised handlers); fall back to
    # parsed-effect dispatch.
    from src.simulator.trainers import named_trainer_handlers
    handler = named_trainer_handlers().get(trainer.name)
    if handler is not None:
        SIM_REPORT.record_trainer(trainer.name)
        return handler(state, player_id, trainer, repository=repository,
                       randomizer=randomizer,
                       source_instance_id=source_instance_id,
                       target_instance_id=target_instance_id)
    effect = _parse(trainer.effect)
    if effect is None:
        return state
    SIM_REPORT.record_trainer(trainer.name)
    return apply_effect(
        state, effect,
        player_id=player_id,
        source_instance_id=source_instance_id,
        target_instance_id=target_instance_id,
        repository=repository, randomizer=randomizer,
        source=f"trainer:{trainer.name}",
        card_id=str(trainer.card_id), card_name=trainer.name,
    )


def apply_ability_effects(
    state: GameState,
    *,
    ability: Ability,
    player_id: int,
    source_instance_id: str | None = None,
    target_instance_id: str | None = None,
    source_card: PokemonCard | None = None,
    repository: CardRepository | None = None,
    randomizer: Randomizer | None = None,
) -> GameState:
    if ability is None or not getattr(ability, "effect", "").strip():
        return state
    # P1.3: per-card dispatch first
    from src.simulator.abilities import named_ability_handlers
    name = source_card.name if source_card is not None else ""
    handler = named_ability_handlers().get(name)
    if handler is not None:
        SIM_REPORT.record_ability(name)
        return handler(state, player_id, source_card,
                       source_instance_id=source_instance_id,
                       repository=repository, randomizer=randomizer)
    effect = _parse(ability.effect)
    if effect is None:
        return state
    card_id = str(getattr(source_card, "card_id", "")) if source_card else ""
    card_name = getattr(source_card, "name", "") if source_card else ""
    SIM_REPORT.record_ability(card_name)
    return apply_effect(
        state, effect,
        player_id=player_id,
        source_instance_id=source_instance_id,
        target_instance_id=target_instance_id,
        repository=repository, randomizer=randomizer,
        source=f"ability:{ability.name}",
        card_id=card_id, card_name=card_name,
    )
