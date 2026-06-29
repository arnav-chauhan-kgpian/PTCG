"""
Repair engine — fixes illegal or structurally broken decks.

Each RepairAction describes one change applied.  The engine applies repairs
in priority order and stops once the deck is legal (or no more repairs apply).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from src.cards.enums import EnergyType
from src.cards.models import EnergyCard, PokemonCard
from src.deck_builder.constraints import ConstraintConfig, check_all, total_count

if TYPE_CHECKING:
    from src.deck_builder.generators import CardIndex


@dataclass
class RepairAction:
    code: str
    message: str
    card_added: str | None = None
    card_removed: str | None = None


@dataclass
class RepairResult:
    slots: dict[str, tuple]    # card_id -> (card, count)
    actions: list[RepairAction] = field(default_factory=list)


class RepairEngine:
    """Applies a sequence of heuristic repairs to bring a deck to legality."""

    def __init__(self, card_index: CardIndex, config: ConstraintConfig | None = None) -> None:
        self._idx = card_index
        self._config = config or ConstraintConfig()

    def repair(self, slots: dict[str, tuple]) -> RepairResult:
        """Mutate a copy of slots until legal or no progress is made."""
        slots = dict(slots)  # shallow copy
        actions: list[RepairAction] = []

        for _ in range(20):  # max iterations
            violations = check_all(slots, self._config)
            errors = [v for v in violations if v.severity == "error"]
            if not errors:
                break
            progress = False
            for v in errors:
                applied = self._apply_repair(v.code, slots, actions)
                if applied:
                    progress = True
                    break
            if not progress:
                break

        # Final size normalisation
        self._normalise_size(slots, actions)
        return RepairResult(slots=slots, actions=actions)

    # ------------------------------------------------------------------
    # Repair handlers
    # ------------------------------------------------------------------

    def _apply_repair(self, code: str, slots: dict, actions: list) -> bool:
        if code == "NO_BASIC_POKEMON":
            return self._add_basic(slots, actions)
        if code == "COPY_LIMIT":
            return self._trim_copies(slots, actions)
        if code == "DECK_SIZE":
            self._normalise_size(slots, actions)
            return True
        if code == "MISSING_PRE_EVOLUTION":
            return self._add_pre_evolutions(slots, actions)
        if code == "ACE_SPEC_LIMIT":
            return self._remove_extra_ace_spec(slots, actions)
        return False

    def _add_basic(self, slots: dict, actions: list) -> bool:
        basics = self._idx.basics()
        if not basics:
            return False
        card = basics[0]
        cid = str(card.card_id)
        if cid in slots:
            _, cnt = slots[cid]
            slots[cid] = (card, cnt + 1)
        else:
            slots[cid] = (card, 1)
        actions.append(RepairAction(
            code="ADD_BASIC",
            message=f"Added Basic Pokémon '{card.name}' — deck had none.",
            card_added=card.name,
        ))
        return True

    def _trim_copies(self, slots: dict, actions: list) -> bool:
        # Group by name
        name_to_ids: dict[str, list[str]] = {}
        for cid, (card, _) in slots.items():
            name_to_ids.setdefault(card.name, []).append(cid)

        for name, ids in name_to_ids.items():
            total = sum(slots[cid][1] for cid in ids)
            # Check if basic energy
            first_card = slots[ids[0]][0]
            if isinstance(first_card, EnergyCard) and first_card.energy_type == EnergyType.BASIC:
                continue
            if total > self._config.max_copies:
                excess = total - self._config.max_copies
                for cid in ids:
                    card, cnt = slots[cid]
                    if excess <= 0:
                        break
                    remove = min(cnt, excess)
                    new_cnt = cnt - remove
                    if new_cnt <= 0:
                        del slots[cid]
                    else:
                        slots[cid] = (card, new_cnt)
                    excess -= remove
                    actions.append(RepairAction(
                        code="TRIM_COPIES",
                        message=f"Trimmed '{name}' from {cnt} to {max(0, cnt - remove)} copies.",
                        card_removed=name,
                    ))
                return True
        return False

    def _add_pre_evolutions(self, slots: dict, actions: list) -> bool:
        names_in_deck = {card.name for card, _ in slots.values()}
        for card, _ in list(slots.values()):
            if isinstance(card, PokemonCard) and card.previous_stage:
                if card.previous_stage not in names_in_deck:
                    # Find the pre-evolution
                    prev_cards = self._idx.by_name(card.previous_stage)
                    if prev_cards:
                        prev = prev_cards[0]
                        prev_id = str(prev.card_id)
                        existing_cnt = slots.get(prev_id, (prev, 0))[1]
                        add_cnt = min(4, max(1, 4 - existing_cnt))
                        slots[prev_id] = (prev, existing_cnt + add_cnt)
                        actions.append(RepairAction(
                            code="ADD_PRE_EVO",
                            message=f"Added {add_cnt}× '{prev.name}' for evolution chain.",
                            card_added=prev.name,
                        ))
                        return True
        return False

    def _remove_extra_ace_spec(self, slots: dict, actions: list) -> bool:
        from src.cards.enums import RuleBox
        ace_ids = [cid for cid, (card, _) in slots.items() if card.rule_box == RuleBox.ACE_SPEC]
        if len(ace_ids) > self._config.max_ace_spec:
            for extra_id in ace_ids[self._config.max_ace_spec:]:
                card, cnt = slots[extra_id]
                if cnt > 1:
                    slots[extra_id] = (card, cnt - 1)
                else:
                    del slots[extra_id]
                actions.append(RepairAction(
                    code="REMOVE_ACE_SPEC",
                    message=f"Removed extra ACE SPEC card '{card.name}'.",
                    card_removed=card.name,
                ))
                return True
        return False

    def _normalise_size(self, slots: dict, actions: list) -> None:
        target = self._config.deck_size
        current = total_count(slots)

        if current < target:
            self._pad_to_size(slots, actions, target - current)
        elif current > target:
            self._trim_to_size(slots, actions, current - target)

    def _pad_to_size(self, slots: dict, actions: list, deficit: int) -> None:
        """Add basic energy (or low-cost basics) to reach 60."""
        energies = [e for e in self._idx.energies() if e.energy_type == EnergyType.BASIC]
        if not energies:
            energies = self._idx.energies()

        # Prefer energy types already in deck
        in_deck_types: set[str] = set()
        for card, _ in slots.values():
            if isinstance(card, EnergyCard):
                for pt in card.provides:
                    in_deck_types.add(pt.value)

        preferred = [e for e in energies if any(pt.value in in_deck_types for pt in e.provides)]
        fill_cards = preferred or energies

        if not fill_cards:
            fill_cards = self._idx.basics()

        for card in fill_cards:
            if deficit <= 0:
                break
            cid = str(card.card_id)
            existing_cnt = slots.get(cid, (card, 0))[1]
            # Basic energy: unlimited; others: cap at 4
            if isinstance(card, EnergyCard) and card.energy_type == EnergyType.BASIC:
                cap = deficit
            else:
                cap = max(0, self._config.max_copies - existing_cnt)
            add = min(deficit, cap)
            if add <= 0:
                continue
            slots[cid] = (card, existing_cnt + add)
            actions.append(RepairAction(
                code="PAD_SIZE",
                message=f"Added {add}× '{card.name}' to reach 60.",
                card_added=card.name,
            ))
            deficit -= add

    def _trim_to_size(self, slots: dict, actions: list, excess: int) -> None:
        """Remove lowest-value cards until at 60."""
        # Priority for removal: energy > low-count duplicates > orphaned trainers
        # Simplified: remove from energy first
        energy_ids = [
            cid for cid, (card, _) in slots.items()
            if isinstance(card, EnergyCard)
        ]
        for cid in energy_ids:
            if excess <= 0:
                break
            card, cnt = slots[cid]
            remove = min(cnt, excess)
            new_cnt = cnt - remove
            if new_cnt <= 0:
                del slots[cid]
            else:
                slots[cid] = (card, new_cnt)
            actions.append(RepairAction(
                code="TRIM_SIZE",
                message=f"Removed {remove}× '{card.name}' to reach 60.",
                card_removed=card.name,
            ))
            excess -= remove
