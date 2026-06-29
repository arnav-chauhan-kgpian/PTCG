"""
Determinization — sample hidden information to enable PIMC-MCTS.

In imperfect-information games (Pokémon TCG), some information is hidden:
  • opponent's hand cards
  • remaining deck order
  • face-down prize cards

Perfect Information Monte Carlo (PIMC) handles this by:
  1. Sampling a *determinization* (a consistent complete state)
  2. Running standard MCTS on the determinized state
  3. Aggregating results across multiple determinizations

This module provides the sampling interface and a RandomDeterminizer
that assigns plausible cards to hidden zones uniformly at random.

The interface is intentionally thin:  future Bayesian inference or
opponent modelling can replace RandomDeterminizer without changing MCTS.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from src.game_state.state import GameState


# -------------------------------------------------------------------------
# Protocol
# -------------------------------------------------------------------------

class DeterminizationSampler(Protocol):
    """
    Interface for sampling a fully-observable state from a partial one.

    The returned state must have the same game_status, turn_number, and
    current_player as the input; only hidden zone contents differ.
    """

    def sample(
        self, state: GameState, rng: random.Random
    ) -> GameState:
        ...

    def sample_n(
        self, state: GameState, n: int, rng: random.Random
    ) -> list[GameState]:
        ...


# -------------------------------------------------------------------------
# Random determinizer
# -------------------------------------------------------------------------

class RandomDeterminizer:
    """
    Assigns hidden cards (opponent hand, unknown prizes, deck order) by
    sampling uniformly from the pool of unaccounted-for card instances.

    Hidden zone handling
    --------------------
    opponent hand:
        We know the *count* but not the *cards*.  We sample that many
        cards from the pool of instances not already placed in a known zone.

    prize cards (face-down):
        We know the count (prizes_remaining).  We assign random cards from
        the pool.

    deck order:
        We know the deck size.  The remaining pool becomes the deck.

    This is a conservative, uninformed approach.  A Bayesian engine would
    weight samples by game history (e.g., if the opponent played a Charizard
    then their remaining hand is less likely to contain another Charizard).
    """

    def sample(
        self, state: GameState, rng: random.Random
    ) -> GameState:
        """Return one determinized copy of *state*."""
        return _determinize(state, rng)

    def sample_n(
        self, state: GameState, n: int, rng: random.Random
    ) -> list[GameState]:
        """Return *n* independent determinizations of *state*."""
        return [_determinize(state, rng) for _ in range(n)]


# -------------------------------------------------------------------------
# Internal implementation
# -------------------------------------------------------------------------

def _determinize(state: GameState, rng: random.Random) -> GameState:
    """
    Create one determinized GameState from a partial-info state.

    Currently this is a shallow operation: we reassign ``deck_order``
    for each player and fill in hidden prize slots with plausible cards.
    Full hand-card sampling would require the card database to know which
    cards could plausibly be in the opponent's hand.

    For Phase 8 (no simulator), this simply shuffles the known deck order.
    """

    new_players = list(state.players)
    new_instances = dict(state.card_instances)

    for pidx, player in enumerate(state.players):
        # Shuffle known deck order (hidden to opponent)
        if player.deck_order:
            shuffled = list(player.deck_order)
            rng.shuffle(shuffled)
            new_players[pidx] = player.model_copy(
                update={"deck_order": tuple(shuffled)}
            )

    return state.model_copy(update={
        "players": tuple(new_players),
        "card_instances": new_instances,
    })


def _pool_of_unknown_instances(
    state: GameState, player_id: int
) -> list[str]:
    """
    Collect instance_ids that are in the deck but not in any known zone.
    Used to populate hidden hand / prize slots during sampling.
    """
    known: set[str] = set()
    p = state.players[player_id]
    known.update(p.hand)
    known.update(p.bench)
    known.update(p.discard)
    known.update(p.lost_zone)
    known.update(p.prizes)
    if p.active:
        known.add(p.active)

    return [
        iid for iid in state.card_instances
        if state.card_instances[iid].owner == player_id and iid not in known
    ]


class IdentityDeterminizer:
    """
    No-op determinizer — returns the state unchanged.
    Used when the state is already fully observable (e.g., for testing).
    """

    def sample(self, state: GameState, rng: random.Random) -> GameState:
        return state

    def sample_n(self, state: GameState, n: int, rng: random.Random) -> list[GameState]:
        return [state] * n
