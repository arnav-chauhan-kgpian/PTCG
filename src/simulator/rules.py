"""
PTCG rules constants and configuration.

Values reflect the Standard format used by the Kaggle competition.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GameRules:
    """Constants used by the simulator.  Override only for non-standard play."""

    deck_size: int = 60
    max_copies_per_card: int = 4
    starting_hand_size: int = 7
    prize_count: int = 6
    bench_size: int = 5
    max_turns: int = 200                # safety cap to prevent infinite games
    supporter_per_turn: int = 1
    energy_attach_per_turn: int = 1
    stadium_per_turn: int = 1
    retreat_per_turn: int = 1
    weakness_multiplier: int = 2
    resistance_reduction: int = 30
    # Turn 1 rules: first player cannot attack on turn 1
    first_player_no_attack_turn_1: bool = True
    # Mulligan: opponent draws +1 per mulligan
    mulligan_bonus_card: bool = True
    max_mulligans: int = 12              # safety cap


DEFAULT_RULES = GameRules()


# Energy token shorthand
ENERGY_TOKENS = {"{R}", "{W}", "{G}", "{L}", "{P}", "{F}",
                 "{D}", "{M}", "{N}", "{C}", "{Y}"}
COLORLESS = "{C}"
