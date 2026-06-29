"""
REAL evaluation using a deck that actually terminates.

Three head-to-head matchups, each n games, all measured:
  A. Random vs Random (baseline distribution)
  B. Heuristic-MCTS Agent vs Random
  C. Heuristic-MCTS Agent vs Heuristic-MCTS Agent (mirror sanity)
"""
from __future__ import annotations

import csv
import json
import math
import os
import pathlib
import random
import statistics
import time
from collections import Counter

os.environ.setdefault("POKEMON_AI_LOG_LEVEL", "ERROR")

OUT = pathlib.Path(__file__).parent / "evaluation"
OUT.mkdir(parents=True, exist_ok=True)


def build_stacked_deck(repo):
    """Stacked aggro: 4× of the top 5 cheap-attack basics + basic energy."""
    from src.cards.enums import Stage
    from src.cards.models import EnergyCard, PokemonCard
    candidates = []
    for c in repo.list_all():
        if isinstance(c, PokemonCard) and c.stage == Stage.BASIC and c.attacks:
            for att in c.attacks:
                cost_n = att.cost.total_count if att.cost else 99
                if cost_n <= 2 and att.damage and att.damage.base >= 20:
                    candidates.append((c, cost_n, att.damage.base))
                    break
    candidates.sort(key=lambda x: (x[1], -x[2]))
    top5 = [c for c, _, _ in candidates[:5]]
    if len(top5) < 5:
        raise RuntimeError("not enough cheap attackers in repo")
    deck: list[int] = []
    for c in top5:
        deck.extend([c.card_id] * 4)  # 20 Pokémon
    energies = [c for c in repo.list_all() if isinstance(c, EnergyCard)]
    basic_energy = next(
        (e for e in energies if "Basic" in (e.name or "")),
        energies[0] if energies else None,
    )
    deck.extend([basic_energy.card_id] * (60 - len(deck)))
    deck_metadata = {
        "top_attackers": [c.name for c in top5],
        "basic_energy": basic_energy.name,
        "energy_count": 60 - 20,
        "pokemon_count": 20,
    }
    return deck[:60], deck_metadata


def wilson_ci(k, n, z=1.96):
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    denom = 1 + z * z / n
    c = (p + z * z / (2 * n)) / denom
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, c - h), min(1.0, c + h))


def play_game(sim, deck_a, deck_b, policy_a, policy_b, max_actions=600, seed=0):
    rng = random.Random(seed)
    state = sim.start_game(deck_a, deck_b)
    actions = 0
    latencies_a = []
    while actions < max_actions:
        if sim.is_terminal(state):
            break
        legal = sim.legal_actions(state)
        if not legal:
            break
        pid = state.current_player
        policy = policy_a if pid == 0 else policy_b
        t0 = time.perf_counter()
        action = policy(state, legal, rng)
        if pid == 0:
            latencies_a.append((time.perf_counter() - t0) * 1000.0)
        state = sim.apply_action(state, action)
        actions += 1
    # Outcome
    from src.game_state.zones import GameStatus
    winner = None
    if state.game_status == GameStatus.PLAYER_0_WIN:
        winner = 0
    elif state.game_status == GameStatus.PLAYER_1_WIN:
        winner = 1
    elif state.game_status == GameStatus.DRAW:
        winner = "draw"
    else:
        winner = "timeout"
    return {
        "winner": winner,
        "actions": actions,
        "final_turn": state.turn_number,
        "p0_prizes_left": state.players[0].prizes_remaining,
        "p1_prizes_left": state.players[1].prizes_remaining,
        "knockouts": len(state.knockout_history),
        "avg_decision_ms_p0": statistics.mean(latencies_a) if latencies_a else 0.0,
        "max_decision_ms_p0": max(latencies_a) if latencies_a else 0.0,
    }


def random_policy(state, legal, rng):
    return rng.choice(legal)


def make_agent_policy(repo, iterations=30):
    from src.competition.agent import AgentConfig, CompetitionAgent
    agent = CompetitionAgent.load(
        None, repository=repo,
        config=AgentConfig(iterations=iterations, time_budget_s=2.0),
    )
    def policy(state, legal, rng):
        action = agent.choose_action(state)
        return action if action is not None else rng.choice(legal)
    return policy, agent


def run_match(label, sim_factory, deck_a, deck_b, policy_a, policy_b,
              n_games, max_actions):
    print(f"\n=== {label} (n={n_games}, action_cap={max_actions}) ===")
    rows = []
    for i in range(n_games):
        sim = sim_factory(seed=500 + i)
        r = play_game(sim, deck_a, deck_b, policy_a, policy_b,
                       max_actions=max_actions, seed=600 + i)
        rows.append({"game_id": i, **r})
        w = r["winner"]
        print(f"  g{i}: winner={w!s:<7} actions={r['actions']:>3} "
              f"prizes=({r['p0_prizes_left']},{r['p1_prizes_left']}) "
              f"kos={r['knockouts']} avg_ms={r['avg_decision_ms_p0']:.0f}")
    return rows


def summarize(label, rows):
    n = len(rows)
    p0_wins = sum(1 for r in rows if r["winner"] == 0)
    p1_wins = sum(1 for r in rows if r["winner"] == 1)
    draws = sum(1 for r in rows if r["winner"] == "draw")
    timeouts = sum(1 for r in rows if r["winner"] == "timeout")
    p0_win_rate = p0_wins / n if n else 0
    ci_lo, ci_hi = wilson_ci(p0_wins, n)
    avg_actions = statistics.mean(r["actions"] for r in rows) if rows else 0
    avg_kos = statistics.mean(r["knockouts"] for r in rows) if rows else 0
    latencies = [r["avg_decision_ms_p0"] for r in rows if r["avg_decision_ms_p0"] > 0]
    avg_lat = statistics.mean(latencies) if latencies else 0
    max_lat = max((r["max_decision_ms_p0"] for r in rows), default=0)
    return {
        "label": label,
        "n_games": n,
        "p0_wins": p0_wins, "p1_wins": p1_wins,
        "draws": draws, "timeouts": timeouts,
        "p0_win_rate": round(p0_win_rate, 4),
        "p0_win_rate_wilson_95_ci": [round(ci_lo, 4), round(ci_hi, 4)],
        "avg_actions_per_game": round(avg_actions, 1),
        "avg_knockouts_per_game": round(avg_kos, 1),
        "avg_decision_latency_ms_p0": round(avg_lat, 1),
        "max_decision_latency_ms_p0": round(max_lat, 1),
    }


def main():
    from src.cards import load_repository
    from src.simulator import PokemonTCGSimulator

    repo = load_repository()
    deck, meta = build_stacked_deck(repo)
    print(f"Stacked aggro deck: {len(deck)} cards, {len(set(deck))} unique")
    print(f"Attackers: {meta['top_attackers']}")
    print(f"Energy: {meta['basic_energy']} × {meta['energy_count']}")

    def sim_factory(seed=0):
        return PokemonTCGSimulator(repo, seed=seed)

    n_games = 20
    max_actions = 500
    agent_iters = 30
    agent_policy_0, _ = make_agent_policy(repo, iterations=agent_iters)
    agent_policy_1, _ = make_agent_policy(repo, iterations=agent_iters)

    # A. Random vs Random
    rows_rr = run_match("A: Random vs Random", sim_factory, deck, deck,
                         random_policy, random_policy, n_games, max_actions)
    # B. Agent vs Random
    rows_ar = run_match("B: Agent vs Random", sim_factory, deck, deck,
                         agent_policy_0, random_policy, n_games, max_actions)
    # C. Agent vs Agent (mirror)
    rows_aa = run_match("C: Agent vs Agent (mirror)", sim_factory, deck, deck,
                         agent_policy_0, agent_policy_1, max(n_games // 2, 6),
                         max_actions)

    summaries = {
        "deck": meta,
        "config": {
            "n_games_per_match": n_games,
            "max_actions_per_game": max_actions,
            "agent_iterations": agent_iters,
        },
        "matches": [
            summarize("random_vs_random", rows_rr),
            summarize("agent_vs_random", rows_ar),
            summarize("agent_vs_agent_mirror", rows_aa),
        ],
    }

    # Save CSVs + JSON
    for name, rows in [
        ("random_vs_random", rows_rr),
        ("agent_vs_random", rows_ar),
        ("agent_vs_agent_mirror", rows_aa),
    ]:
        with (OUT / f"{name}.csv").open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

    (OUT / "summary.json").write_text(
        json.dumps(summaries, indent=2, default=str), encoding="utf-8"
    )
    print("\nSUMMARY:")
    for s in summaries["matches"]:
        print(f"  {s['label']:<25} p0_win={s['p0_win_rate']:.1%} "
              f"CI={s['p0_win_rate_wilson_95_ci']} "
              f"draws/to={s['draws']}/{s['timeouts']} "
              f"avg_actions={s['avg_actions_per_game']}")
    print(f"\n→ {OUT/'summary.json'}")


if __name__ == "__main__":
    main()
