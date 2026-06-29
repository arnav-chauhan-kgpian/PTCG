"""
Lean eval that completes in minutes, not hours.

Strategy: random-vs-random is free (no MCTS). Agent matches use small N and
low MCTS iterations to fit in budget. All three matches in <5 minutes.
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

os.environ.setdefault("POKEMON_AI_LOG_LEVEL", "ERROR")

OUT = pathlib.Path(__file__).parent / "evaluation"
OUT.mkdir(parents=True, exist_ok=True)


def build_stacked_deck(repo):
    from src.cards.enums import Stage
    from src.cards.models import EnergyCard, PokemonCard
    cands = []
    for c in repo.list_all():
        if isinstance(c, PokemonCard) and c.stage == Stage.BASIC and c.attacks:
            for att in c.attacks:
                cost_n = att.cost.total_count if att.cost else 99
                if cost_n <= 2 and att.damage and att.damage.base >= 20:
                    cands.append((c, cost_n, att.damage.base))
                    break
    cands.sort(key=lambda x: (x[1], -x[2]))
    top5 = [c for c, _, _ in cands[:5]]
    deck: list[int] = []
    for c in top5:
        deck.extend([c.card_id] * 4)
    energies = [c for c in repo.list_all() if isinstance(c, EnergyCard)]
    basic = next((e for e in energies if "Basic" in (e.name or "")), energies[0])
    deck.extend([basic.card_id] * (60 - len(deck)))
    return deck[:60], {
        "top_attackers": [c.name for c in top5],
        "basic_energy": basic.name,
        "energy_count": 40, "pokemon_count": 20,
    }


def wilson_ci(k, n, z=1.96):
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def play(sim, deck, pa, pb, max_actions=400, seed=0):
    rng = random.Random(seed)
    state = sim.start_game(deck, deck)
    n = 0
    lats = []
    while n < max_actions and not sim.is_terminal(state):
        legal = sim.legal_actions(state)
        if not legal:
            break
        pid = state.current_player
        t0 = time.perf_counter()
        a = (pa if pid == 0 else pb)(state, legal, rng)
        if pid == 0:
            lats.append((time.perf_counter() - t0) * 1000.0)
        state = sim.apply_action(state, a)
        n += 1
    from src.game_state.zones import GameStatus
    winner = (
        0 if state.game_status == GameStatus.PLAYER_0_WIN
        else 1 if state.game_status == GameStatus.PLAYER_1_WIN
        else "draw" if state.game_status == GameStatus.DRAW
        else "timeout"
    )
    return {
        "winner": winner, "actions": n,
        "final_turn": state.turn_number,
        "p0_prizes_left": state.players[0].prizes_remaining,
        "p1_prizes_left": state.players[1].prizes_remaining,
        "knockouts": len(state.knockout_history),
        "avg_ms_p0": round(statistics.mean(lats), 2) if lats else 0.0,
        "max_ms_p0": round(max(lats), 2) if lats else 0.0,
    }


def run_match(label, sim_factory, deck, pa, pb, n, max_actions):
    print(f"\n=== {label}  n={n}")
    rows = []
    for i in range(n):
        sim = sim_factory(seed=500 + i)
        r = play(sim, deck, pa, pb, max_actions=max_actions, seed=600 + i)
        rows.append({"game_id": i, **r})
        print(f"  g{i}: winner={r['winner']!s:<7} actions={r['actions']:>3} "
              f"prizes=({r['p0_prizes_left']},{r['p1_prizes_left']}) "
              f"kos={r['knockouts']} avg_ms={r['avg_ms_p0']}")
    return rows


def summarize(label, rows):
    n = len(rows)
    p0_w = sum(1 for r in rows if r["winner"] == 0)
    p1_w = sum(1 for r in rows if r["winner"] == 1)
    d = sum(1 for r in rows if r["winner"] == "draw")
    t = sum(1 for r in rows if r["winner"] == "timeout")
    p0_wr = p0_w / n if n else 0
    lo, hi = wilson_ci(p0_w, n)
    lats = [r["avg_ms_p0"] for r in rows if r["avg_ms_p0"] > 0]
    return {
        "label": label, "n_games": n,
        "p0_wins": p0_w, "p1_wins": p1_w, "draws": d, "timeouts": t,
        "p0_win_rate": round(p0_wr, 4),
        "p0_win_rate_wilson_95_ci": [round(lo, 4), round(hi, 4)],
        "avg_actions_per_game": round(statistics.mean(r["actions"] for r in rows), 1),
        "avg_knockouts_per_game": round(statistics.mean(r["knockouts"] for r in rows), 1),
        "termination_rate": round(
            sum(1 for r in rows if r["winner"] != "timeout") / n, 4
        ) if n else 0,
        "avg_decision_ms_p0": round(statistics.mean(lats), 1) if lats else 0,
        "max_decision_ms_p0": round(max((r["max_ms_p0"] for r in rows), default=0), 1),
    }


def main():
    from src.cards import load_repository
    from src.competition.agent import AgentConfig, CompetitionAgent
    from src.simulator import PokemonTCGSimulator

    repo = load_repository()
    deck, meta = build_stacked_deck(repo)
    print(f"deck: {len(deck)} cards / {len(set(deck))} unique")
    print(f"attackers: {meta['top_attackers']}")

    def sim_factory(seed=0):
        return PokemonTCGSimulator(repo, seed=seed)

    def random_pol(state, legal, rng):
        return rng.choice(legal)

    # Lean agent: 8 iterations (≈70 ms/decision), reusable across both agent roles
    agent_lo = CompetitionAgent.load(
        None, repository=repo, config=AgentConfig(iterations=8, time_budget_s=1.0)
    )
    agent_hi = CompetitionAgent.load(
        None, repository=repo, config=AgentConfig(iterations=8, time_budget_s=1.0)
    )

    def agent_pol_lo(state, legal, rng):
        a = agent_lo.choose_action(state)
        return a if a is not None else rng.choice(legal)

    def agent_pol_hi(state, legal, rng):
        a = agent_hi.choose_action(state)
        return a if a is not None else rng.choice(legal)

    # A. Random vs Random — fast baseline, 30 games
    rows_rr = run_match("A: Random vs Random", sim_factory, deck,
                         random_pol, random_pol, n=30, max_actions=400)

    # B. Agent vs Random — 15 games at 8 iterations
    rows_ar = run_match("B: Agent(8 iter) vs Random", sim_factory, deck,
                         agent_pol_lo, random_pol, n=15, max_actions=400)

    # C. Agent mirror — 8 games sanity check
    rows_aa = run_match("C: Agent(8) mirror", sim_factory, deck,
                         agent_pol_lo, agent_pol_hi, n=8, max_actions=400)

    summaries = {
        "deck": meta,
        "config": {
            "max_actions_per_game": 400,
            "agent_iterations": 8,
        },
        "matches": [
            summarize("random_vs_random", rows_rr),
            summarize("agent_vs_random", rows_ar),
            summarize("agent_vs_agent_mirror", rows_aa),
        ],
    }

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
              f"term_rate={s['termination_rate']:.0%} "
              f"avg_actions={s['avg_actions_per_game']}")


if __name__ == "__main__":
    main()
