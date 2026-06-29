"""
Trainer card execution — items, supporters, stadiums, tools.

Effects are dispatched on keywords extracted from the card's effect text.
This is intentionally heuristic: unknown trainers no-op (the card is
still moved to the discard pile, just without additional effect).
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from src.cards.models import TrainerCard
from src.game_state.state import GameState
from src.simulator import zones as Z

if TYPE_CHECKING:
    from src.cards.repository import CardRepository
    from src.simulator.randomizer import Randomizer


_DRAW_RE = re.compile(r"draw\s+(\d+)\s+cards?", re.IGNORECASE)
_DRAW_UNTIL_RE = re.compile(r"draw\s+cards\s+until\s+you\s+have\s+(\d+)", re.IGNORECASE)
_HEAL_RE = re.compile(r"heal\s+(\d+)\s+damage", re.IGNORECASE)


def execute_trainer(
    state: GameState,
    player_id: int,
    trainer: TrainerCard,
    repository: CardRepository,
    randomizer: Randomizer,
    target_pokemon_id: str | None = None,
) -> GameState:
    """Resolve a trainer card's primary effect."""
    effect_text = (trainer.effect or "").lower()

    # Draw N cards
    m = _DRAW_RE.search(effect_text)
    if m:
        n = int(m.group(1))
        state = _draw_n(state, player_id, n)

    # Draw until you have N cards
    m = _DRAW_UNTIL_RE.search(effect_text)
    if m:
        target = int(m.group(1))
        current = state.players[player_id].hand_count
        state = _draw_n(state, player_id, max(0, target - current))

    # Heal damage
    m = _HEAL_RE.search(effect_text)
    if m and target_pokemon_id is not None:
        amount = int(m.group(1))
        from src.simulator.attack_engine import heal
        state = heal(state, target_pokemon_id, amount)

    # Switch your active and benched (rough match: "Switch your Active")
    if "switch your active" in effect_text or "switch your" in effect_text:
        player = state.players[player_id]
        if player.bench:
            state = Z.swap_active_with_bench(state, player_id, 0)

    return state


def _draw_n(state: GameState, player_id: int, n: int) -> GameState:
    for _ in range(n):
        state, drawn = Z.move_to_hand_from_deck(state, player_id)
        if drawn is None:
            break
    return state
