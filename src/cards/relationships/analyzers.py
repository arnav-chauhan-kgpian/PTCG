"""
Analyzers — each extracts a specific category of edges from cards.

Each analyzer implements a single `analyze(cards) → list[CardEdge]` method.
The builder calls all analyzers and merges their outputs.
"""

from __future__ import annotations

import re
from collections import defaultdict

from src.cards.effects.actions import ActionTag
from src.cards.effects.compiler import compile_card
from src.cards.effects.models import (
    AbilitySuppression,
    AttachEnergy,
    BenchDamage,
    CompositeEffect,
    DrawCards,
    Effect,
    ForceSwitch,
    HealEffect,
    KnockOut,
    MillEffect,
    MoveEnergy,
    PreventDamage,
    SearchDeck,
    StatusConditionEffect,
    SwitchActive,
)
from src.cards.enums import PokemonType, TrainerType
from src.cards.models import EnergyCard, PokemonCard, TrainerCard
from src.cards.relationships.edges import make_edge, make_pair
from src.cards.relationships.models import CardEdge, RelationshipType
from src.cards.types import AnyCard

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _card_id(card: AnyCard) -> str:
    return str(card.card_id)


def _all_effects(eff: Effect) -> list[Effect]:
    """Flatten composite / conditional effects into a flat list."""
    from src.cards.effects.models import CoinFlip, ConditionalEffect
    out = [eff]
    if isinstance(eff, CompositeEffect):
        for step in eff.steps:
            out.extend(_all_effects(step))
    if isinstance(eff, ConditionalEffect):
        out.extend(_all_effects(eff.then_effect))
        if eff.else_effect:
            out.extend(_all_effects(eff.else_effect))
    if isinstance(eff, CoinFlip):
        for outcome in eff.outcomes:
            out.extend(_all_effects(outcome.effect))
        if eff.per_heads_effect:
            out.extend(_all_effects(eff.per_heads_effect))
    return out


# ---------------------------------------------------------------------------
# 1. Evolution analyzer
# ---------------------------------------------------------------------------


class EvolutionAnalyzer:
    """Generates EVOLVES_FROM / EVOLVES_TO edges from Pokémon stage data."""

    def analyze(self, cards: list[AnyCard]) -> list[CardEdge]:
        # Build name → card_id map
        pokemon = [c for c in cards if isinstance(c, PokemonCard)]
        name_to_ids: dict[str, list[str]] = defaultdict(list)
        for p in pokemon:
            name_to_ids[p.name.lower()].append(_card_id(p))

        edges: list[CardEdge] = []
        for p in pokemon:
            if p.previous_stage is None:
                continue
            prev_ids = name_to_ids.get(p.previous_stage.lower(), [])
            for prev_id in prev_ids:
                edges.extend(make_pair(
                    _card_id(p), prev_id,
                    RelationshipType.EVOLVES_FROM,
                    reason=f"{p.name} evolves from {p.previous_stage}",
                    confidence=1.0,
                    evidence=(f"stage={p.stage.value}", f"previous_stage={p.previous_stage}"),
                ))
        return edges


# ---------------------------------------------------------------------------
# 2. Effect analyzer — reads parsed effects
# ---------------------------------------------------------------------------


class EffectAnalyzer:
    """Infers edges from the compiled semantic effects of each card."""

    # Map ActionTag → RelationshipType
    _TAG_TO_REL: dict[ActionTag, RelationshipType] = {
        ActionTag.DRAW_CARDS:        RelationshipType.DRAW_ENGINE,
        ActionTag.HEAL:              RelationshipType.HEALS,
        ActionTag.DISCARD_ENERGY:    RelationshipType.DISCARD_ENGINE,
        ActionTag.SEARCH_DECK:       RelationshipType.SEARCHES_FOR,
        ActionTag.ATTACH_ENERGY:     RelationshipType.ACCELERATES_ENERGY,
        ActionTag.MOVE_ENERGY:       RelationshipType.ACCELERATES_ENERGY,
        ActionTag.INFLICT_STATUS:    RelationshipType.SPECIAL_CONDITION,
        ActionTag.SELF_STATUS:       RelationshipType.SPECIAL_CONDITION,
        ActionTag.DAMAGE_MODIFIER:   RelationshipType.DAMAGE_BOOST,
        ActionTag.BENCH_DAMAGE:      RelationshipType.DAMAGE_BOOST,
        ActionTag.SELF_DAMAGE:       RelationshipType.SELF_SETUP,
        ActionTag.SWITCH_ACTIVE:     RelationshipType.SWITCHES,
        ActionTag.FORCE_SWITCH:      RelationshipType.SWITCHES,
        ActionTag.PREVENT_DAMAGE:    RelationshipType.PROTECTS,
        ActionTag.ABILITY_SUPPRESSION: RelationshipType.ABILITY_COUNTER,
        ActionTag.SHUFFLE_DECK:       RelationshipType.CONSISTENCY,
        ActionTag.MILL:               RelationshipType.ANTI_META,
        ActionTag.RETURN_TO_HAND:     RelationshipType.RECOVERY,
        ActionTag.KNOCK_OUT:          RelationshipType.FINISHER,
        ActionTag.EVOLVE:             RelationshipType.SELF_SETUP,
        ActionTag.COPY_ATTACK:        RelationshipType.BENCH_SUPPORT,
    }

    def analyze(self, cards: list[AnyCard]) -> list[CardEdge]:
        # pokemon_type → list[card_id] for energy synergy
        pokemon_by_type: dict[PokemonType, list[str]] = defaultdict(list)
        for c in cards:
            if isinstance(c, PokemonCard):
                pokemon_by_type[c.pokemon_type].append(_card_id(c))

        # energy that provides each type
        energy_by_type: dict[PokemonType, list[str]] = defaultdict(list)
        for c in cards:
            if isinstance(c, EnergyCard):
                for ptype in c.provides:
                    energy_by_type[ptype].append(_card_id(c))

        edges: list[CardEdge] = []

        for card in cards:
            src = _card_id(card)
            try:
                compiled = compile_card(card)
            except Exception:
                continue

            all_card_effects: list[Effect] = []
            for eff in compiled.attack_effects.values():
                all_card_effects.extend(_all_effects(eff))
            if compiled.ability_effect:
                all_card_effects.extend(_all_effects(compiled.ability_effect))
            if compiled.trainer_effect:
                all_card_effects.extend(_all_effects(compiled.trainer_effect))
            if compiled.energy_effect:
                all_card_effects.extend(_all_effects(compiled.energy_effect))

            for eff in all_card_effects:
                tag = eff.action_type
                rel = self._TAG_TO_REL.get(tag)
                if rel is None:
                    continue

                # Self-referential edge: trainer/energy → all Pokémon of relevant type
                if isinstance(card, (TrainerCard, EnergyCard)):
                    # Attach energy → connect energy accelerator to Pokémon of that type
                    if isinstance(eff, (AttachEnergy, MoveEnergy)):
                        etype = eff.energy_type
                        if etype is not None:
                            for poke_id in pokemon_by_type.get(etype, []):
                                if poke_id != src:
                                    edges.append(make_edge(
                                        src, poke_id, rel,
                                        reason=f"accelerates {etype.value} energy",
                                        confidence=0.8,
                                        evidence=("effect:attach_energy",),
                                    ))
                    elif isinstance(eff, DrawCards):
                        # Draw trainers support everything — add self label
                        edges.append(make_edge(
                            src, src, RelationshipType.CONSISTENCY,
                            reason="draw engine",
                            confidence=0.9,
                            evidence=("effect:draw_cards",),
                        ))
                    elif isinstance(eff, HealEffect):
                        for poke_id in [_card_id(c) for c in cards if isinstance(c, PokemonCard)]:
                            if poke_id != src:
                                edges.append(make_edge(
                                    src, poke_id, rel,
                                    reason="heals Pokémon",
                                    confidence=0.5,
                                    evidence=("effect:heal",),
                                    weight=0.4,
                                ))
                    elif isinstance(eff, SearchDeck):
                        edges.append(make_edge(
                            src, src, RelationshipType.CONSISTENCY,
                            reason=f"search deck for {eff.card_type}",
                            confidence=0.85,
                            evidence=("effect:search_deck",),
                        ))
                    elif isinstance(eff, (SwitchActive, ForceSwitch)):
                        edges.append(make_edge(
                            src, src, RelationshipType.SWITCHES,
                            reason="switching support",
                            confidence=0.8,
                            evidence=("effect:switch",),
                        ))
                    elif isinstance(eff, AbilitySuppression):
                        edges.append(make_edge(
                            src, src, RelationshipType.ABILITY_COUNTER,
                            reason="suppresses abilities",
                            confidence=0.9,
                            evidence=("effect:ability_suppress",),
                        ))
                    elif isinstance(eff, PreventDamage):
                        edges.append(make_edge(
                            src, src, RelationshipType.PROTECTS,
                            reason="prevents damage",
                            confidence=0.85,
                            evidence=("effect:prevent_damage",),
                        ))
                    elif isinstance(eff, MillEffect):
                        edges.append(make_edge(
                            src, src, RelationshipType.ANTI_META,
                            reason="mills opponent's deck",
                            confidence=0.75,
                            evidence=("effect:mill",),
                        ))

                elif isinstance(card, PokemonCard):
                    if isinstance(eff, DrawCards):
                        edges.append(make_edge(
                            src, src, RelationshipType.DRAW_ENGINE,
                            reason="draws cards via attack/ability",
                            confidence=0.7,
                            evidence=("effect:draw_cards",),
                        ))
                    elif isinstance(eff, HealEffect):
                        edges.append(make_edge(
                            src, src, RelationshipType.HEALS,
                            reason="heals via attack/ability",
                            confidence=0.7,
                            evidence=("effect:heal",),
                        ))
                    elif isinstance(eff, (AttachEnergy, MoveEnergy)):
                        etype = getattr(eff, 'energy_type', None)
                        if etype:
                            for en_id in energy_by_type.get(etype, []):
                                edges.append(make_edge(
                                    src, en_id, RelationshipType.USES_ENERGY,
                                    reason=f"uses {etype.value} energy",
                                    confidence=0.7,
                                    evidence=("effect:attach_energy",),
                                ))
                    elif isinstance(eff, KnockOut):
                        edges.append(make_edge(
                            src, src, RelationshipType.FINISHER,
                            reason="can knock out via effect",
                            confidence=0.7,
                            evidence=("effect:knock_out",),
                        ))
                    elif isinstance(eff, AbilitySuppression):
                        edges.append(make_edge(
                            src, src, RelationshipType.ABILITY_COUNTER,
                            reason="ability suppresses opponent abilities",
                            confidence=0.85,
                            evidence=("effect:ability_suppress",),
                        ))
                    elif isinstance(eff, PreventDamage):
                        edges.append(make_edge(
                            src, src, RelationshipType.PROTECTS,
                            reason="prevents damage via ability/attack",
                            confidence=0.8,
                            evidence=("effect:prevent_damage",),
                        ))
                    elif isinstance(eff, StatusConditionEffect):
                        edges.append(make_edge(
                            src, src, RelationshipType.SPECIAL_CONDITION,
                            reason=f"inflicts {eff.condition.value}",
                            confidence=0.75,
                            evidence=("effect:status",),
                        ))
                    elif isinstance(eff, BenchDamage):
                        edges.append(make_edge(
                            src, src, RelationshipType.DAMAGE_BOOST,
                            reason="deals bench damage",
                            confidence=0.7,
                            evidence=("effect:bench_damage",),
                        ))

        return edges


# ---------------------------------------------------------------------------
# 3. Energy synergy analyzer
# ---------------------------------------------------------------------------


class EnergyAnalyzer:
    """Links Pokémon to energy cards that match their attack requirements."""

    def analyze(self, cards: list[AnyCard]) -> list[CardEdge]:
        pokemon = [c for c in cards if isinstance(c, PokemonCard)]
        energies = [c for c in cards if isinstance(c, EnergyCard)]

        # energy_id → set of PokemonType it provides
        energy_provides: dict[str, set[PokemonType]] = {}
        for e in energies:
            energy_provides[_card_id(e)] = set(e.provides)

        edges: list[CardEdge] = []
        for p in pokemon:
            # Collect all energy types required by this Pokémon's attacks
            required_types: set[PokemonType] = set()
            for attack in p.attacks:
                for token in attack.cost.tokens:
                    # Map symbol to type
                    _SYM: dict[str, PokemonType] = {
                        "{G}": PokemonType.GRASS,   "{R}": PokemonType.FIRE,
                        "{W}": PokemonType.WATER,   "{L}": PokemonType.LIGHTNING,
                        "{P}": PokemonType.PSYCHIC, "{F}": PokemonType.FIGHTING,
                        "{D}": PokemonType.DARK,    "{M}": PokemonType.METAL,
                        "{C}": PokemonType.COLORLESS,
                    }
                    pt = _SYM.get(token)
                    if pt:
                        required_types.add(pt)

            pid = _card_id(p)
            for en in energies:
                eid = _card_id(en)
                if not en.provides:
                    continue
                if any(pt in required_types for pt in en.provides):
                    rel = RelationshipType.ENERGY_SYNERGY if en.effect else RelationshipType.USES_ENERGY
                    confidence = 0.9 if not en.effect else 0.7
                    edges.extend(make_pair(
                        pid, eid, rel,
                        reason=f"{p.name} needs {', '.join(pt.value for pt in required_types & set(en.provides))}",
                        confidence=confidence,
                        evidence=(f"requires_types={[pt.value for pt in required_types]}",),
                    ))

        # Special energy to special energy synergy (both colorless providers)
        special = [e for e in energies if e.effect]
        for i, e1 in enumerate(special):
            for e2 in special[i + 1:]:
                # If they provide the same types, they might be alternatives
                if set(e1.provides) & set(e2.provides):
                    edges.append(make_edge(
                        _card_id(e1), _card_id(e2), RelationshipType.ENERGY_SYNERGY,
                        reason="overlapping energy provision",
                        confidence=0.4,
                        evidence=("energy_overlap",),
                    ))

        return edges


# ---------------------------------------------------------------------------
# 4. Text reference analyzer
# ---------------------------------------------------------------------------

# Match card names inside quotes or after "search for a card named"
_NAME_REF = re.compile(
    r"""
    (?:
        search \s+ your \s+ deck \s+ for \s+ (?:a|an)? \s*  # search for
        | named \s+                                           # named X
        | choose \s+ (?:a|1) \s+                             # choose a
        | put \s+ (?:a|an|1) \s+                             # put a
    )
    ([A-Z][A-Za-z\s\-éèê']+?)                                # name candidate
    (?:\s+card)?                                              # optional "card"
    (?:[,.\s]|$)
    """,
    re.VERBOSE | re.IGNORECASE,
)


class TextReferenceAnalyzer:
    """Finds explicit card name references in effect text."""

    def analyze(self, cards: list[AnyCard]) -> list[CardEdge]:
        # Build name index (lowercase → card_ids)
        name_index: dict[str, list[str]] = defaultdict(list)
        for c in cards:
            name_index[c.name.lower()].append(_card_id(c))
            # Also index base names without "ex" / "V" suffix for partial matching
            base = re.sub(r'\s+(?:ex|V|VMAX|VSTAR|GX|EX)\s*$', '', c.name, flags=re.I).strip().lower()
            if base != c.name.lower():
                name_index[base].append(_card_id(c))

        edges: list[CardEdge] = []

        for card in cards:
            src = _card_id(card)
            text = ""
            if isinstance(card, PokemonCard):
                texts = []
                if card.ability:
                    texts.append(card.ability.effect)
                if card.tera_ability:
                    texts.append(card.tera_ability.effect)
                for a in card.attacks:
                    texts.append(a.effect)
                text = " ".join(texts)
            elif isinstance(card, TrainerCard):
                text = card.effect
            elif isinstance(card, EnergyCard):
                text = card.effect

            for m in _NAME_REF.finditer(text):
                candidate = m.group(1).strip().lower()
                target_ids = name_index.get(candidate, [])
                for tid in target_ids:
                    if tid == src:
                        continue
                    edges.append(make_edge(
                        src, tid, RelationshipType.SEARCHES_FOR,
                        reason=f"text references '{m.group(1).strip()}'",
                        confidence=0.7,
                        evidence=(f"text_ref:{m.group(0).strip()[:50]}",),
                    ))
                    edges.append(make_edge(
                        tid, src, RelationshipType.SEARCHED_BY,
                        reason=f"referenced by '{card.name}'",
                        confidence=0.7,
                        evidence=("text_ref_inverse",),
                    ))

        return edges


# ---------------------------------------------------------------------------
# 5. Trainer role analyzer
# ---------------------------------------------------------------------------


class TrainerRoleAnalyzer:
    """Assigns trainer-category relationship edges to Pokémon they generally support."""

    def analyze(self, cards: list[AnyCard]) -> list[CardEdge]:
        trainers = [c for c in cards if isinstance(c, TrainerCard)]
        pokemon = [c for c in cards if isinstance(c, PokemonCard)]

        edges: list[CardEdge] = []
        for t in trainers:
            tid = _card_id(t)

            # Tag trainers with their own role
            role_map = {
                TrainerType.ITEM:         RelationshipType.ITEM_SUPPORT,
                TrainerType.SUPPORTER:    RelationshipType.SUPPORTER_SUPPORT,
                TrainerType.STADIUM:      RelationshipType.STADIUM_SUPPORT,
                TrainerType.POKEMON_TOOL: RelationshipType.TOOL_SUPPORT,
            }
            role_rel = role_map.get(t.trainer_type, RelationshipType.ITEM_SUPPORT)

            # Trainers with draw effects are draw engines
            _DRAW_PATTERNS = re.compile(r'draw \d+ cards?', re.I)
            _SEARCH_PATTERNS = re.compile(r'search your deck', re.I)
            _HEAL_PATTERNS = re.compile(r'heal \d+ damage', re.I)
            _SWITCH_PATTERNS = re.compile(r'switch(?:ed)? (?:your|this)', re.I)
            _ENERGY_PATTERNS = re.compile(r'attach .{0,40} energy', re.I)
            _RECOVER_PATTERNS = re.compile(r'from your discard', re.I)

            effect_text = t.effect

            if _DRAW_PATTERNS.search(effect_text):
                edges.append(make_edge(tid, tid, RelationshipType.DRAW_ENGINE,
                    reason="draw trainer", confidence=0.9, evidence=("text_match:draw",)))
            if _SEARCH_PATTERNS.search(effect_text):
                edges.append(make_edge(tid, tid, RelationshipType.CONSISTENCY,
                    reason="search trainer", confidence=0.85, evidence=("text_match:search",)))
            if _HEAL_PATTERNS.search(effect_text):
                edges.append(make_edge(tid, tid, RelationshipType.HEALS,
                    reason="heal trainer", confidence=0.85, evidence=("text_match:heal",)))
            if _SWITCH_PATTERNS.search(effect_text):
                edges.append(make_edge(tid, tid, RelationshipType.SWITCHES,
                    reason="switch trainer", confidence=0.85, evidence=("text_match:switch",)))
            if _ENERGY_PATTERNS.search(effect_text):
                edges.append(make_edge(tid, tid, RelationshipType.ACCELERATES_ENERGY,
                    reason="energy acceleration trainer", confidence=0.85, evidence=("text_match:energy",)))
            if _RECOVER_PATTERNS.search(effect_text):
                edges.append(make_edge(tid, tid, RelationshipType.RECOVERY,
                    reason="recovery trainer", confidence=0.80, evidence=("text_match:recover",)))

        return edges


# ---------------------------------------------------------------------------
# 6. Type synergy analyzer
# ---------------------------------------------------------------------------


class TypeSynergyAnalyzer:
    """Cards of the same Pokémon type share a weak TYPE_SYNERGY edge."""

    def analyze(self, cards: list[AnyCard]) -> list[CardEdge]:
        pokemon = [c for c in cards if isinstance(c, PokemonCard)]

        # Group by type
        by_type: dict[PokemonType, list[str]] = defaultdict(list)
        for p in pokemon:
            by_type[p.pokemon_type].append(_card_id(p))

        edges: list[CardEdge] = []
        for ptype, ids in by_type.items():
            for i, id1 in enumerate(ids):
                for id2 in ids[i + 1:]:
                    edges.append(make_edge(
                        id1, id2, RelationshipType.TYPE_SYNERGY,
                        reason=f"same type: {ptype.value}",
                        confidence=0.4,
                        evidence=(f"type={ptype.value}",),
                    ))
                    edges.append(make_edge(
                        id2, id1, RelationshipType.TYPE_SYNERGY,
                        reason=f"same type: {ptype.value}",
                        confidence=0.4,
                        evidence=(f"type={ptype.value}",),
                    ))
        return edges
