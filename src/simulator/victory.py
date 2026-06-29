"""
Victory condition checking.

Three ways to win in PTCG:
1. Take your last prize card (prizes_remaining = 0)
2. Opponent has no Pokémon in play (active + bench empty)
3. Opponent must draw and their deck is empty (deck-out)

Returns the new game status and winner.
"""

from __future__ import annotations

from src.game_state.state import GameState
from src.game_state.zones import GameStatus


def check_victory(state: GameState) -> tuple[GameStatus, int | None]:
    """
    Return (new_status, winner) reflecting the current state.

    If still ongoing, returns (ONGOING, None).
    """
    p0, p1 = state.players

    # 1. Prize victory
    p0_done = p0.prizes_remaining == 0
    p1_done = p1.prizes_remaining == 0
    if p0_done and p1_done:
        # Simultaneous — treat as draw
        return GameStatus.DRAW, None
    if p0_done:
        return GameStatus.PLAYER_0_WIN, 0
    if p1_done:
        return GameStatus.PLAYER_1_WIN, 1

    # 2. No Pokémon in play
    p0_no_poke = p0.active is None and len(p0.bench) == 0
    p1_no_poke = p1.active is None and len(p1.bench) == 0
    if p0_no_poke and p1_no_poke:
        return GameStatus.DRAW, None
    if p0_no_poke:
        return GameStatus.PLAYER_1_WIN, 1
    if p1_no_poke:
        return GameStatus.PLAYER_0_WIN, 0

    return GameStatus.ONGOING, None


def apply_victory_check(state: GameState) -> GameState:
    """Update game_status if a victory condition has been met.

    Once a terminal status is set (deck-out, prize win, no-Pokémon loss),
    later checks must not overwrite it back to ONGOING.
    """
    if state.game_status not in (GameStatus.NOT_STARTED, GameStatus.ONGOING):
        return state
    status, winner = check_victory(state)
    if status == state.game_status:
        return state
    return state.with_status(status, winner)


def is_deckout_loss(state: GameState, player_id: int) -> bool:
    """True if *player_id* would lose by being unable to draw."""
    return state.players[player_id].deck_size == 0
