"""
CardIndex and ConstructiveGenerator.

CardIndex wraps the full card database for fast lookup by name, id, type, stage.
ConstructiveGenerator builds a deck in 10 staged steps from a BuildRequest.
"""

from __future__ import annotations

import random
from collections import defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from src.cards.enums import EnergyType, PokemonType, Stage
from src.cards.models import EnergyCard, PokemonCard, TrainerCard
from src.cards.types import AnyCard
from src.deck_builder.constraints import ConstraintConfig, total_count

if TYPE_CHECKING:
    from src.cards.relationships.graph import CardGraph
    from src.cards.relationships.traversal import GraphTraversal


# ---------------------------------------------------------------------------
# Card Index
# ---------------------------------------------------------------------------

class CardIndex:
    """Fast multi-key lookup over the full card database."""

    def __init__(self, cards: list[AnyCard]) -> None:
        self._all: list[AnyCard] = cards
        self._by_id: dict[str, AnyCard] = {str(c.card_id): c for c in cards}
        self._by_name: dict[str, list[AnyCard]] = defaultdict(list)
        self._pokemon: list[PokemonCard] = []
        self._trainers: list[TrainerCard] = []
        self._energies: list[EnergyCard] = []
        self._by_type: dict[PokemonType, list[PokemonCard]] = defaultdict(list)
        self._by_stage: dict[Stage, list[PokemonCard]] = defaultdict(list)
        self._draw_trainers: list[TrainerCard] = []
        self._search_trainers: list[TrainerCard] = []
        self._recovery_trainers: list[TrainerCard] = []
        self._switch_trainers: list[TrainerCard] = []
        self._disruption_trainers: list[TrainerCard] = []
        self._energy_accel: list[AnyCard] = []
        self._basics: list[PokemonCard] = []

        self._build_index(cards)

    def _build_index(self, cards: list[AnyCard]) -> None:
        _DRAW_KW = ("draw", "draw a card", "draw cards", "draw until", "draw 2", "draw 3",
                    "draw 4", "draw 5", "draw 6", "draw 7")
        _SEARCH_KW = ("search your deck", "look at the top", "put a card from your deck",
                      "search for", "from your deck")
        _RECOVERY_KW = ("from your discard", "discard pile", "retrieve", "recover")
        _SWITCH_KW = ("switch", "retreat for free", "move.*active", "gust")
        _DISRUPTION_KW = ("discard a card", "your opponent discards", "shuffle.*hand",
                          "can't use abilities", "lock", "blocked")
        _ACCEL_KW = ("attach.*energy", "attach an energy", "energy from", "accelerate")

        for card in cards:
            self._by_name[card.name.lower()].append(card)
            if isinstance(card, PokemonCard):
                self._pokemon.append(card)
                self._by_type[card.pokemon_type].append(card)
                self._by_stage[card.stage].append(card)
                if card.stage == Stage.BASIC:
                    self._basics.append(card)
                # Check ability for acceleration
                if card.ability:
                    text = card.ability.effect.lower()
                    if any(k in text for k in _ACCEL_KW):
                        self._energy_accel.append(card)
            elif isinstance(card, TrainerCard):
                self._trainers.append(card)
                text = card.effect.lower()
                if any(k in text for k in _DRAW_KW):
                    self._draw_trainers.append(card)
                if any(k in text for k in _SEARCH_KW):
                    self._search_trainers.append(card)
                if any(k in text for k in _RECOVERY_KW):
                    self._recovery_trainers.append(card)
                if any(k in text for k in _SWITCH_KW):
                    self._switch_trainers.append(card)
                if any(k in text for k in _DISRUPTION_KW):
                    self._disruption_trainers.append(card)
                if any(k in text for k in _ACCEL_KW):
                    self._energy_accel.append(card)
            elif isinstance(card, EnergyCard):
                self._energies.append(card)

    # --- Lookup ---

    def by_id(self, card_id: str) -> AnyCard | None:
        return self._by_id.get(str(card_id))

    def by_name(self, name: str) -> list[AnyCard]:
        return self._by_name.get(name.lower(), [])

    def all_cards(self) -> list[AnyCard]:
        return self._all

    def pokemon(self) -> list[PokemonCard]:
        return self._pokemon

    def trainers(self) -> list[TrainerCard]:
        return self._trainers

    def energies(self) -> list[EnergyCard]:
        return self._energies

    def basics(self) -> list[PokemonCard]:
        return self._basics

    def pokemon_by_type(self, ptype: PokemonType) -> list[PokemonCard]:
        return self._by_type.get(ptype, [])

    def pokemon_by_stage(self, stage: Stage) -> list[PokemonCard]:
        return self._by_stage.get(stage, [])

    def draw_trainers(self) -> list[TrainerCard]:
        return self._draw_trainers

    def search_trainers(self) -> list[TrainerCard]:
        return self._search_trainers

    def recovery_trainers(self) -> list[TrainerCard]:
        return self._recovery_trainers

    def switch_trainers(self) -> list[TrainerCard]:
        return self._switch_trainers

    def disruption_trainers(self) -> list[TrainerCard]:
        return self._disruption_trainers

    def energy_accel_cards(self) -> list[AnyCard]:
        return self._energy_accel

    def basic_energies_for_type(self, ptype: PokemonType) -> list[EnergyCard]:
        return [e for e in self._energies
                if e.energy_type == EnergyType.BASIC
                and ptype in e.provides]

    def any_basic_energies(self) -> list[EnergyCard]:
        return [e for e in self._energies if e.energy_type == EnergyType.BASIC]


# ---------------------------------------------------------------------------
# Build request
# ---------------------------------------------------------------------------

@dataclass
class BuildRequest:
    seed_cards: list[str] = field(default_factory=list)     # names or str IDs
    pokemon_type: PokemonType | None = None
    archetype: str | None = None
    playstyle: str | None = None
    partial_deck_slots: dict[str, tuple] | None = None
    existing_deck_slots: dict[str, tuple] | None = None
    constraint_config: ConstraintConfig = field(default_factory=ConstraintConfig)
    n_candidates: int = 5
    search_strategy: str = "beam"
    objective_weights: dict[str, float] = field(default_factory=dict)
    max_iterations: int = 40
    seed: int | None = None


# ---------------------------------------------------------------------------
# Constructive Generator (10 stages)
# ---------------------------------------------------------------------------

class ConstructiveGenerator:
    """
    Builds a deck slot-by-slot in 10 ordered stages.
    Each stage is independently overridable.
    """

    TARGET = 60
    CORE_COUNT = 3       # copies of main attacker
    EVO_COUNTS = {Stage.STAGE_2: 2, Stage.STAGE_1: 3, Stage.BASIC: 4}

    def __init__(
        self,
        card_index: CardIndex,
        graph: CardGraph,
        traversal: GraphTraversal,
        config: ConstraintConfig | None = None,
        rng: random.Random | None = None,
    ) -> None:
        self._idx = card_index
        self._graph = graph
        self._t = traversal
        self._cfg = config or ConstraintConfig()
        self._rng = rng or random.Random()

    # --- Main entry ---

    def generate(self, request: BuildRequest) -> dict[str, tuple]:
        """Generate a slot dict implementing all 10 stages."""
        slots: dict[str, tuple] = {}

        if request.partial_deck_slots:
            slots = dict(request.partial_deck_slots)
        elif request.existing_deck_slots:
            slots = dict(request.existing_deck_slots)

        # Stage 1: Core engine
        core_ids = self._stage1_core(slots, request)
        # Stage 2: Evolution lines
        self._stage2_evolutions(slots, core_ids, request)
        # Stage 3: Support Pokémon
        self._stage3_support_pokemon(slots, core_ids, request)
        # Stage 4: Draw engine
        self._stage4_draw(slots, core_ids)
        # Stage 5: Search engine
        self._stage5_search(slots, core_ids)
        # Stage 6: Disruption
        self._stage6_disruption(slots, core_ids, request)
        # Stage 7: Recovery
        self._stage7_recovery(slots)
        # Stage 8: Switching
        self._stage8_switching(slots)
        # Stage 9: Energy package
        self._stage9_energy(slots, core_ids)
        # Stage 10: Trim/pad to 60
        self._stage10_normalise(slots)

        return slots

    # ------------------------------------------------------------------
    # Stages
    # ------------------------------------------------------------------

    def _stage1_core(self, slots: dict, request: BuildRequest) -> list[str]:
        """Select 2–4 copies of main attacker(s). Return their card IDs."""
        core_ids: list[str] = []

        # Resolve seed cards by name or ID
        for seed in request.seed_cards:
            found = self._idx.by_id(seed) or (self._idx.by_name(seed) or [None])[0]
            if found is None:
                continue
            cid = str(found.card_id)
            if cid not in slots:
                count = self.EVO_COUNTS.get(getattr(found, "stage", None), self.CORE_COUNT)
                slots[cid] = (found, min(count, self._cfg.max_copies))
            core_ids.append(cid)

        # If no seeds, pick by archetype or type
        if not core_ids:
            core_ids = self._pick_core_by_request(slots, request)

        return core_ids

    def _pick_core_by_request(self, slots: dict, request: BuildRequest) -> list[str]:
        pool: list[PokemonCard] = []

        if request.pokemon_type:
            pool = self._idx.pokemon_by_type(request.pokemon_type)
        if not pool:
            pool = self._idx.pokemon()

        # Filter by archetype preference
        arch = (request.archetype or "").lower()
        if arch in ("aggro", "single prize", "fast"):
            # Prefer Basic with high damage
            pool = [p for p in pool if p.stage == Stage.BASIC] or pool
            pool = sorted(pool, key=lambda p: max(
                (a.damage.base for a in p.attacks), default=0
            ), reverse=True)
        elif arch in ("combo", "energy ramp"):
            # Prefer Stage 2 with high cost attacks
            pool = sorted(pool, key=lambda p: (
                p.stage == Stage.STAGE_2,
                max((a.damage.base for a in p.attacks), default=0)
            ), reverse=True)
        else:
            pool = sorted(pool, key=lambda p: max(
                (a.damage.base for a in p.attacks), default=0
            ), reverse=True)

        core_ids: list[str] = []
        for card in pool[:3]:
            cid = str(card.card_id)
            if cid not in slots:
                count = self.EVO_COUNTS.get(card.stage, self.CORE_COUNT)
                slots[cid] = (card, min(count, self._cfg.max_copies))
            core_ids.append(cid)

        return core_ids

    def _stage2_evolutions(self, slots: dict, core_ids: list[str], request: BuildRequest) -> None:
        """Add pre-evolutions for any Stage 1/2 core cards."""
        processed: set[str] = set()
        for cid in list(core_ids):
            card, _ = slots.get(cid, (None, 0))
            if card is None or not isinstance(card, PokemonCard):
                continue
            self._fill_evolution_chain(slots, card, processed)

    def _fill_evolution_chain(
        self,
        slots: dict,
        card: PokemonCard,
        processed: set[str],
    ) -> None:
        if card.name in processed:
            return
        processed.add(card.name)
        if not card.previous_stage:
            return
        prev_cards = self._idx.by_name(card.previous_stage)
        if not prev_cards:
            return
        prev = next((c for c in prev_cards if isinstance(c, PokemonCard)), None)
        if prev is None:
            return
        prev_id = str(prev.card_id)
        target_count = self.EVO_COUNTS.get(prev.stage, 4)
        existing = slots.get(prev_id, (prev, 0))[1]
        if existing < target_count:
            slots[prev_id] = (prev, target_count)
        # Recurse
        self._fill_evolution_chain(slots, prev, processed)

    def _stage3_support_pokemon(
        self, slots: dict, core_ids: list[str], request: BuildRequest
    ) -> None:
        """Add 1–2 synergy Pokémon partners."""
        if total_count(slots) >= self.TARGET - 20:
            return

        for cid in core_ids[:2]:
            partners = self._t.recommend_partners(cid, top_n=15)
            added = 0
            for pid in partners:
                if total_count(slots) >= self.TARGET - 18:
                    break
                node = self._graph.node(pid)
                if node is None or node.card_super_type.value != "pokemon":
                    continue
                pcard = self._idx.by_id(pid)
                if pcard is None or pid in slots:
                    continue
                slots[pid] = (pcard, 2)
                added += 1
                if added >= 2:
                    break

    def _stage4_draw(self, slots: dict, core_ids: list[str]) -> None:
        """Add draw engine trainers: target ~12 draw cards."""
        current_draw = sum(
            count for _, (card, count) in slots.items()
            if isinstance(card, TrainerCard) and any(
                k in card.effect.lower() for k in ("draw", "draw a card")
            )
        )
        target = 12
        if current_draw >= target:
            return

        draw_pool = self._ranked_trainers(self._idx.draw_trainers(), core_ids)
        self._fill_trainers(slots, draw_pool, target - current_draw, max_per_card=4)

    def _stage5_search(self, slots: dict, core_ids: list[str]) -> None:
        """Add search trainers: target ~8 search cards."""
        current_search = sum(
            count for _, (card, count) in slots.items()
            if isinstance(card, TrainerCard) and any(
                k in card.effect.lower() for k in ("search your deck", "from your deck")
            )
        )
        target = 8
        if current_search >= target:
            return
        search_pool = self._ranked_trainers(self._idx.search_trainers(), core_ids)
        self._fill_trainers(slots, search_pool, target - current_search, max_per_card=4)

    def _stage6_disruption(
        self, slots: dict, core_ids: list[str], request: BuildRequest
    ) -> None:
        """Add disruption cards for Control/Mill archetypes."""
        arch = (request.archetype or "").lower()
        if arch not in ("control", "mill", "stall", "disruption"):
            return
        disruption_pool = self._ranked_trainers(self._idx.disruption_trainers(), core_ids)
        self._fill_trainers(slots, disruption_pool, 6, max_per_card=4)

    def _stage7_recovery(self, slots: dict) -> None:
        """Add 2–4 recovery cards."""
        if total_count(slots) >= self.TARGET - 10:
            return
        recovery_pool = self._idx.recovery_trainers()
        self._fill_trainers(slots, recovery_pool, 4, max_per_card=2)

    def _stage8_switching(self, slots: dict) -> None:
        """Add 2–4 switch cards."""
        if total_count(slots) >= self.TARGET - 6:
            return
        switch_pool = self._idx.switch_trainers()
        self._fill_trainers(slots, switch_pool, 4, max_per_card=2)

    def _stage9_energy(self, slots: dict, core_ids: list[str]) -> None:
        """Add energy package: type-appropriate basic energies."""
        if total_count(slots) >= self.TARGET:
            return

        # Determine required types from core attackers
        required_types: list[PokemonType] = []
        for cid in core_ids:
            card, _ = slots.get(cid, (None, 0))
            if card is None or not isinstance(card, PokemonCard):
                continue
            for attack in card.attacks:
                for token in attack.cost.tokens:
                    if token not in ("{C}", "{A}"):
                        try:
                            pt = PokemonType(token)
                            if pt not in required_types:
                                required_types.append(pt)
                        except ValueError:
                            pass

        # Also check energy acceleration cards via graph
        for cid in core_ids:
            pkg = self._t.find_energy_package(cid)
            for eid in pkg[:3]:
                ecard = self._idx.by_id(eid)
                if ecard is not None and isinstance(ecard, EnergyCard):
                    e_id = str(ecard.card_id)
                    if e_id not in slots:
                        slots[e_id] = (ecard, 2)

        deficit = self.TARGET - total_count(slots)
        if deficit <= 0:
            return

        # Pick basic energies for required types
        if not required_types:
            required_types = [PokemonType.COLORLESS]

        for ptype in required_types:
            energy_pool = self._idx.basic_energies_for_type(ptype)
            if not energy_pool:
                energy_pool = self._idx.any_basic_energies()
            if not energy_pool:
                break
            ecard = energy_pool[0]
            ecid = str(ecard.card_id)
            per_type = max(4, deficit // len(required_types))
            existing = slots.get(ecid, (ecard, 0))[1]
            slots[ecid] = (ecard, existing + per_type)
            deficit -= per_type
            if deficit <= 0:
                break

        # Pad any remainder with the first available basic energy
        if deficit > 0:
            fallback = self._idx.any_basic_energies()
            if fallback:
                ecid = str(fallback[0].card_id)
                existing = slots.get(ecid, (fallback[0], 0))[1]
                slots[ecid] = (fallback[0], existing + deficit)

    def _stage10_normalise(self, slots: dict) -> None:
        """Trim or pad slots to exactly 60."""
        current = total_count(slots)
        target = self.TARGET

        if current < target:
            # Pad with energy
            self._stage9_energy(slots, [])

        current = total_count(slots)
        if current > target:
            # Trim energy first, then lowest-copy trainers
            excess = current - target
            energy_ids = [cid for cid, (c, _) in slots.items() if isinstance(c, EnergyCard)]
            for cid in energy_ids:
                if excess <= 0:
                    break
                card, cnt = slots[cid]
                remove = min(cnt - 1, excess) if cnt > 1 else min(cnt, excess)
                if remove <= 0:
                    continue
                new_cnt = cnt - remove
                if new_cnt <= 0:
                    del slots[cid]
                else:
                    slots[cid] = (card, new_cnt)
                excess -= remove

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _ranked_trainers(
        self, pool: list[TrainerCard], core_ids: list[str]
    ) -> list[TrainerCard]:
        """Sort trainers by their synergy with core cards."""
        deck_ids = set(core_ids)
        scores: dict[str, float] = {}
        for trainer in pool:
            tid = str(trainer.card_id)
            # Count synergy edges from trainer to deck cards
            synergy = sum(
                1 for e in self._graph.edges_from(tid)
                if e.target in deck_ids
            )
            scores[tid] = synergy
        return sorted(pool, key=lambda t: -scores.get(str(t.card_id), 0))

    def _fill_trainers(
        self,
        slots: dict,
        pool: list,
        n_cards: int,
        max_per_card: int = 4,
    ) -> None:
        added = 0
        for card in pool:
            if added >= n_cards or total_count(slots) >= self.TARGET - 8:
                break
            cid = str(card.card_id)
            existing = slots.get(cid, (card, 0))[1]
            if existing >= max_per_card:
                continue
            take = min(max_per_card - existing, n_cards - added, self._cfg.max_copies - existing)
            if take <= 0:
                continue
            slots[cid] = (card, existing + take)
            added += take
