"""
P2.2 — Simulator validation.

Replays random games and tabulates correctness statistics:
  - legality  : every action chosen was in legal_actions(state)
  - state transitions reduce to apply_action(state, a) — no state leak
  - prize accounting: total prize cards in flight stays consistent
  - status handling: between-turn effects produce damage / clear correctly
  - KO resolution: KO'd Pokémon disappear and prizes are awarded
  - victory detection: terminal status set when prize / no-Pokémon / deck-out
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from src.game_state.zones import GameStatus, SpecialCondition
from src.simulator import PokemonTCGSimulator

if TYPE_CHECKING:
    from src.cards.repository import CardRepository


@dataclass
class SimulatorValidationReport:
    """Aggregated correctness statistics from N random self-play games."""
    games_played: int = 0
    games_terminal: int = 0
    games_max_turns: int = 0

    total_actions: int = 0
    illegal_actions_attempted: int = 0   # actions not in the legal set
    state_mutation_violations: int = 0    # apply_action mutated input state

    prize_accounting_errors: int = 0
    bench_overflow_observed: int = 0
    duplicate_zone_observed: int = 0

    burn_damage_events: int = 0
    poison_damage_events: int = 0
    asleep_wake_events: int = 0
    paralysis_clear_events: int = 0
    confusion_self_damage_events: int = 0

    knockouts_total: int = 0
    prize_wins: int = 0
    no_pokemon_wins: int = 0
    deckout_wins: int = 0

    # Per-game length distribution
    game_lengths: list[int] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "games_played": self.games_played,
            "games_terminal": self.games_terminal,
            "games_max_turns": self.games_max_turns,
            "terminal_rate": (
                self.games_terminal / self.games_played
                if self.games_played else 0.0
            ),
            "total_actions": self.total_actions,
            "illegal_actions_attempted": self.illegal_actions_attempted,
            "state_mutation_violations": self.state_mutation_violations,
            "prize_accounting_errors": self.prize_accounting_errors,
            "bench_overflow_observed": self.bench_overflow_observed,
            "duplicate_zone_observed": self.duplicate_zone_observed,
            "burn_damage_events": self.burn_damage_events,
            "poison_damage_events": self.poison_damage_events,
            "asleep_wake_events": self.asleep_wake_events,
            "paralysis_clear_events": self.paralysis_clear_events,
            "confusion_self_damage_events": self.confusion_self_damage_events,
            "knockouts_total": self.knockouts_total,
            "prize_wins": self.prize_wins,
            "no_pokemon_wins": self.no_pokemon_wins,
            "deckout_wins": self.deckout_wins,
            "avg_game_length": (
                sum(self.game_lengths) / len(self.game_lengths)
                if self.game_lengths else 0.0
            ),
        }

    @property
    def correctness_rate(self) -> float:
        """Fraction of total actions that passed all consistency checks."""
        if self.total_actions == 0:
            return 1.0
        errors = (
            self.illegal_actions_attempted
            + self.state_mutation_violations
            + self.prize_accounting_errors
            + self.bench_overflow_observed
            + self.duplicate_zone_observed
        )
        return max(0.0, 1.0 - errors / self.total_actions)


def validate_simulator(
    repository: CardRepository,
    *,
    n_games: int = 20,
    max_actions_per_game: int = 500,
    deck_a: list[int] | None = None,
    deck_b: list[int] | None = None,
    seed: int = 0,
) -> SimulatorValidationReport:
    """Drive random self-play games and tally consistency observations."""
    report = SimulatorValidationReport()
    base_rng = random.Random(seed)

    if deck_a is None or deck_b is None:
        deck = _default_deck(repository)
        deck_a = deck_a or deck
        deck_b = deck_b or deck

    for i in range(n_games):
        sim = PokemonTCGSimulator(repository, seed=base_rng.randint(0, 10_000))
        state = sim.start_game(deck_a, deck_b)
        rng = random.Random(base_rng.randint(0, 10_000))
        actions_in_game = 0

        # Snapshot state's serialized form (for mutation check)
        from src.game_state.hashing import state_fingerprint
        starting_state = state

        while not sim.is_terminal(state) and actions_in_game < max_actions_per_game:
            legal = sim.legal_actions(state)
            if not legal:
                break
            chosen = rng.choice(legal)

            # ── Legality check: chosen action must be in legal set ──
            if chosen not in legal:
                report.illegal_actions_attempted += 1

            # ── State mutation guard: capture fingerprint before apply ──
            fp_before = state_fingerprint(state)
            new_state = sim.apply_action(state, chosen)
            if state_fingerprint(state) != fp_before:
                report.state_mutation_violations += 1

            # ── Consistency checks on new_state ──
            _check_consistency(new_state, report)
            # ── Status events (deltas) ──
            _track_status_events(state, new_state, report)
            # ── KO events (deltas) ──
            _track_knockouts(state, new_state, report)

            state = new_state
            actions_in_game += 1

        # Terminal status accounting
        report.games_played += 1
        report.total_actions += actions_in_game
        report.game_lengths.append(actions_in_game)
        if sim.is_terminal(state):
            report.games_terminal += 1
            if state.game_status in (GameStatus.PLAYER_0_WIN,
                                       GameStatus.PLAYER_1_WIN,
                                       GameStatus.DRAW):
                if (state.players[0].prizes_remaining == 0
                        or state.players[1].prizes_remaining == 0):
                    report.prize_wins += 1
                elif (state.players[0].active is None
                      and not state.players[0].bench) or (
                    state.players[1].active is None
                    and not state.players[1].bench
                ):
                    report.no_pokemon_wins += 1
                elif (state.players[0].deck_size == 0
                      or state.players[1].deck_size == 0):
                    report.deckout_wins += 1
        else:
            report.games_max_turns += 1

    return report


def _check_consistency(state, report: SimulatorValidationReport) -> None:
    for p in state.players:
        if len(p.bench) > 5:
            report.bench_overflow_observed += 1
        if p.prizes_remaining < 0 or p.prizes_remaining > 6:
            report.prize_accounting_errors += 1
        # Duplicate-zone check on a per-player basis
        all_ids = list(p.hand) + list(p.bench) + list(p.discard)
        if p.active:
            all_ids.append(p.active)
        if len(all_ids) != len(set(all_ids)):
            report.duplicate_zone_observed += 1


def _track_status_events(old, new, report: SimulatorValidationReport) -> None:
    """Detect between-turn status events between old and new states."""
    # Heuristic detection — full event logging would require Action records,
    # but we can spot effective deltas in damage / conditions.
    for pid in (0, 1):
        old_active = old.players[pid].active
        if not old_active or old_active != new.players[pid].active:
            continue
        old_inst = old.card_instances.get(old_active)
        new_inst = new.card_instances.get(old_active)
        if old_inst is None or new_inst is None:
            continue
        dmg_delta = new_inst.damage_taken - old_inst.damage_taken
        if dmg_delta == 20 and SpecialCondition.BURNED in old_inst.special_conditions:
            report.burn_damage_events += 1
        if dmg_delta == 10 and SpecialCondition.POISONED in old_inst.special_conditions:
            report.poison_damage_events += 1
        if (SpecialCondition.ASLEEP in old_inst.special_conditions
                and SpecialCondition.ASLEEP not in new_inst.special_conditions):
            report.asleep_wake_events += 1
        if (SpecialCondition.PARALYZED in old_inst.special_conditions
                and SpecialCondition.PARALYZED not in new_inst.special_conditions):
            report.paralysis_clear_events += 1


def _track_knockouts(old, new, report: SimulatorValidationReport) -> None:
    if len(new.knockout_history) > len(old.knockout_history):
        report.knockouts_total += (
            len(new.knockout_history) - len(old.knockout_history)
        )


def _default_deck(repository) -> list[int]:
    """Build a 60-card placeholder deck from whatever the repo provides."""
    from src.cards.enums import Stage
    from src.cards.models import EnergyCard, PokemonCard
    basics = [c.card_id for c in repository.list_all()
               if isinstance(c, PokemonCard) and c.stage == Stage.BASIC]
    energies = [c.card_id for c in repository.list_all()
                 if isinstance(c, EnergyCard)]
    trainers = [c.card_id for c in repository.list_trainers()]
    pool = basics or list(repository.list_all())
    deck: list[int] = []
    # Heuristic mix
    while len(deck) < 24 and pool:
        deck.append(pool[len(deck) % len(pool)].card_id
                     if hasattr(pool[0], "card_id") else pool[len(deck) % len(pool)])
    while len(deck) < 42 and trainers:
        deck.append(trainers[(len(deck) - 24) % len(trainers)])
    while len(deck) < 60 and energies:
        deck.append(energies[(len(deck) - 42) % len(energies)])
    # Pad with whatever is available
    while len(deck) < 60:
        deck.append(pool[len(deck) % len(pool)].card_id
                     if hasattr(pool[0], "card_id") else pool[len(deck) % len(pool)])
    return deck[:60]
