"""
ROOT CAUSE DIAGNOSTIC — why do games not terminate?

Runs three controlled experiments:
  1. Default deck (the one used in the earlier failed eval).
  2. The Aggro deck the builder picked.
  3. A hand-crafted "must-terminate" deck of 4× a basic with cheap attack.

For each: random-vs-random play, instrumented for every termination
condition the simulator checks.
"""
from __future__ import annotations

import json
import os
import pathlib
import random
from collections import Counter

os.environ.setdefault("POKEMON_AI_LOG_LEVEL", "ERROR")

OUT = pathlib.Path(__file__).parent / "evaluation"
OUT.mkdir(parents=True, exist_ok=True)


def parse_ptcg_live_to_ids(repo, ptcg_live_text: str) -> list[int]:
    """Convert PTCG-Live text into a card_id list, replicating quantities."""
    from src.cards.parser import parse_card_set_collection
    # Simpler: parse line-by-line. Each line: "<qty> <name> <SET> <number>"
    ids: list[int] = []
    name_to_card = {c.name.lower(): c for c in repo.list_all()}
    for line in ptcg_live_text.splitlines():
        line = line.strip()
        if not line or line.startswith(("Pok", "Trainer", "Energy", "Total")):
            continue
        parts = line.split()
        if not parts or not parts[0].isdigit():
            continue
        qty = int(parts[0])
        # Find longest matching name (greedy)
        rest = " ".join(parts[1:])
        match = None
        for name, card in name_to_card.items():
            if rest.lower().startswith(name):
                if match is None or len(name) > len(match[0]):
                    match = (name, card)
        if match:
            ids.extend([match[1].card_id] * qty)
    # Pad to 60 if short
    while len(ids) < 60:
        ids.append(ids[-1] if ids else 1)
    return ids[:60]


def diagnose_one_game(sim, repo, deck_a, deck_b, max_actions=400, seed=0):
    """Run one random-vs-random game and capture rich telemetry."""
    rng = random.Random(seed)
    state = sim.start_game(deck_a, deck_b)
    actions_taken = 0
    turn_numbers = []
    knockouts_seen = 0
    last_prize_change_action = -1
    attacks_attempted = 0
    end_turn_actions = 0
    energy_attaches = 0
    action_type_counts: Counter = Counter()
    prizes_over_time = []
    bench_sizes = []
    deck_sizes = []

    prev_prizes = (state.players[0].prizes_remaining, state.players[1].prizes_remaining)
    prev_kos = len(state.knockout_history)
    prev_turn = state.turn_number

    while actions_taken < max_actions:
        if sim.is_terminal(state):
            break
        legal = sim.legal_actions(state)
        if not legal:
            break
        action = rng.choice(legal)
        action_type_counts[action.action_type] += 1
        if "attack" in action.action_type.lower():
            attacks_attempted += 1
        if "end_turn" in action.action_type.lower():
            end_turn_actions += 1
        if "energy" in action.action_type.lower() or "attach" in action.action_type.lower():
            energy_attaches += 1

        new_state = sim.apply_action(state, action)

        new_prizes = (new_state.players[0].prizes_remaining,
                       new_state.players[1].prizes_remaining)
        if new_prizes != prev_prizes:
            last_prize_change_action = actions_taken
            prev_prizes = new_prizes

        new_kos = len(new_state.knockout_history)
        if new_kos > prev_kos:
            knockouts_seen += new_kos - prev_kos
            prev_kos = new_kos

        if new_state.turn_number != prev_turn:
            turn_numbers.append(new_state.turn_number)
            prev_turn = new_state.turn_number

        prizes_over_time.append(new_prizes)
        bench_sizes.append((len(new_state.players[0].bench), len(new_state.players[1].bench)))
        deck_sizes.append((new_state.players[0].deck_size, new_state.players[1].deck_size))

        state = new_state
        actions_taken += 1

    terminal = sim.is_terminal(state)
    return {
        "actions_taken": actions_taken,
        "terminal": terminal,
        "terminal_reason": (
            "prize_zero" if state.players[0].prizes_remaining == 0
                            or state.players[1].prizes_remaining == 0
            else "no_pokemon" if (state.players[0].active is None and not state.players[0].bench)
                                or (state.players[1].active is None and not state.players[1].bench)
            else "deckout" if state.players[0].deck_size == 0 or state.players[1].deck_size == 0
            else "max_turns" if state.turn_number >= sim.rules.max_turns
            else "action_cap" if not terminal
            else "unknown"
        ),
        "final_turn_number": state.turn_number,
        "final_prizes_p0": state.players[0].prizes_remaining,
        "final_prizes_p1": state.players[1].prizes_remaining,
        "final_deck_p0": state.players[0].deck_size,
        "final_deck_p1": state.players[1].deck_size,
        "knockouts": knockouts_seen,
        "last_prize_change_action": last_prize_change_action,
        "attacks_attempted": attacks_attempted,
        "end_turns": end_turn_actions,
        "energy_attaches": energy_attaches,
        "distinct_action_types": len(action_type_counts),
        "top_actions": action_type_counts.most_common(8),
        "turn_number_advances": len(turn_numbers),
        "max_turn_reached": max(turn_numbers) if turn_numbers else 0,
    }


def run_experiment(name, deck_a, deck_b, repo, n_games=8, max_actions=400):
    from src.simulator import PokemonTCGSimulator
    print(f"\n=== {name} (n={n_games} games, action_cap={max_actions}) ===")
    print(f"  deck_a length: {len(deck_a)}, unique: {len(set(deck_a))}")
    results = []
    for i in range(n_games):
        sim = PokemonTCGSimulator(repo, seed=100 + i)
        r = diagnose_one_game(sim, repo, deck_a, deck_b, max_actions=max_actions, seed=200 + i)
        results.append(r)
        print(f"  g{i}: actions={r['actions_taken']:>3} terminal={r['terminal']:<5} "
              f"reason={r['terminal_reason']:<12} kos={r['knockouts']} "
              f"attacks={r['attacks_attempted']} end_turns={r['end_turns']} "
              f"turn#={r['final_turn_number']} "
              f"prizes=({r['final_prizes_p0']},{r['final_prizes_p1']}) "
              f"deck=({r['final_deck_p0']},{r['final_deck_p1']})")
    return {
        "experiment": name,
        "n_games": n_games,
        "max_actions": max_actions,
        "deck_length": len(deck_a),
        "deck_unique": len(set(deck_a)),
        "termination_rate": sum(1 for r in results if r["terminal"]) / n_games,
        "avg_actions": sum(r["actions_taken"] for r in results) / n_games,
        "avg_kos": sum(r["knockouts"] for r in results) / n_games,
        "avg_attacks": sum(r["attacks_attempted"] for r in results) / n_games,
        "avg_end_turns": sum(r["end_turns"] for r in results) / n_games,
        "avg_turn_number": sum(r["final_turn_number"] for r in results) / n_games,
        "terminal_reasons": Counter(r["terminal_reason"] for r in results),
        "per_game": results,
    }


def main():
    from src.cards import load_repository
    from src.cards.enums import Stage
    from src.cards.models import EnergyCard, PokemonCard
    from src.evaluation.simulator_validation import _default_deck

    repo = load_repository()
    print(f"Repository: {len(repo.list_all())} cards")

    # --- Experiment 1: the default deck (24 unique basics + 18 unique trainers + 18 unique energies) ---
    default = _default_deck(repo)
    print(f"\nDefault deck: {len(default)} cards, {len(set(default))} unique")
    exp1 = run_experiment("default_deck", default, default, repo, n_games=8, max_actions=400)

    # --- Experiment 2: a properly stacked aggro deck (4x copies) ---
    # Pick the cheapest-attack basic Pokémon
    candidates = []
    for c in repo.list_all():
        if isinstance(c, PokemonCard) and c.stage == Stage.BASIC and c.attacks:
            for att in c.attacks:
                cost_n = att.cost.total_count if att.cost else 99
                if cost_n <= 2 and att.damage and att.damage.base >= 20:
                    candidates.append((c, att, cost_n, att.damage.base))
                    break
    candidates.sort(key=lambda x: (x[2], -x[3]))  # cheapest cost, then highest damage
    chosen_basic = candidates[0][0] if candidates else None
    print(f"\nChosen attacker: {chosen_basic.name if chosen_basic else 'NONE'} "
          f"(cost {candidates[0][2]}, damage {candidates[0][3]})" if candidates else "")

    energies = [c for c in repo.list_all() if isinstance(c, EnergyCard)]
    basic_energy = next((e for e in energies if "Basic" in (e.name or "")), energies[0] if energies else None)

    if chosen_basic and basic_energy:
        stacked: list[int] = []
        stacked.extend([chosen_basic.card_id] * 20)   # 20 attackers (5 unique copies of one card? Actually 1 card × 20 is illegal, but let's see what sim accepts)
        # Actually PTCG rule: max 4 copies of any non-basic-energy card.
        # Use 4 copies of 5 different basic attackers to be legal
        # Take top 5 attackers
        top5 = [c for c, _, _, _ in candidates[:5]]
        if len(top5) >= 5:
            stacked = []
            for c in top5:
                stacked.extend([c.card_id] * 4)   # 20 Pokémon
        stacked.extend([basic_energy.card_id] * (60 - len(stacked)))  # rest energy
        stacked = stacked[:60]
        print(f"Stacked aggro deck: {len(stacked)} cards, {len(set(stacked))} unique")
        exp2 = run_experiment("stacked_aggro_4x_5_basics", stacked, stacked, repo,
                                n_games=8, max_actions=400)
    else:
        exp2 = None
        print("Could not assemble stacked aggro — missing basic attacker or basic energy.")

    # --- Experiment 3: the Aggro deck the builder picked earlier ---
    try:
        aggro_json = json.loads(
            (pathlib.Path(__file__).parent / "csv" / "deck_aggro.json").read_text(encoding="utf-8")
        )
        ptcg_text = aggro_json["ptcg_live"]
        builder_ids = parse_ptcg_live_to_ids(repo, ptcg_text)
        print(f"\nBuilder Aggro deck: {len(builder_ids)} cards, "
              f"{len(set(builder_ids))} unique")
        exp3 = run_experiment("builder_aggro", builder_ids, builder_ids, repo,
                                n_games=8, max_actions=400)
    except Exception as exc:
        print(f"Builder aggro parse failed: {exc}")
        exp3 = None

    summary = {
        "experiments": [e for e in (exp1, exp2, exp3) if e is not None],
        "interpretation": (
            "If termination_rate stays 0 even with stacked aggro decks, "
            "the issue is in the simulator's KO/prize-take flow under "
            "random policy. If termination_rate rises with stacked decks, "
            "the original issue is deck composition, not simulator."
        ),
    }
    (OUT / "termination_diagnostic.json").write_text(
        json.dumps(summary, indent=2, default=str),
        encoding="utf-8",
    )
    print(f"\n→ Wrote {OUT/'termination_diagnostic.json'}")
    for e in summary["experiments"]:
        print(f"  {e['experiment']:<40} termination_rate={e['termination_rate']:.0%} "
              f"avg_kos={e['avg_kos']:.1f} avg_attacks={e['avg_attacks']:.1f}")


if __name__ == "__main__":
    main()
