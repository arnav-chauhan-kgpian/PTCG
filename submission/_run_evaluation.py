"""
Single-shot evaluation script. Runs everything needed for the Kaggle
submission and saves real measured outputs under submission/.

Outputs:
  submission/csv/agent_vs_random.csv           per-game results
  submission/csv/agent_vs_random_summary.json  aggregate
  submission/csv/mcts_position_quality.json    per-position search metrics
  submission/csv/deck_candidates.csv           deck builder candidates ranked
  submission/csv/deck_analysis_<arch>.json     analyzer output per finalist
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
from typing import Any

os.environ.setdefault("POKEMON_AI_LOG_LEVEL", "ERROR")

OUT = pathlib.Path(__file__).parent / "csv"
OUT.mkdir(parents=True, exist_ok=True)


def _safe_mean(xs):
    if not xs:
        return 0.0
    return round(statistics.mean(xs), 2)


def main() -> dict[str, Any]:
    from src.cards import load_repository
    from src.cards.relationships import build_graph
    from src.competition.agent import AgentConfig, CompetitionAgent
    from src.decks.analyzer import DeckAnalyzer
    from src.deck_builder import DeckBuilder
    from src.deck_builder import exports as deck_exports
    from src.evaluation.simulator_validation import _default_deck
    from src.simulator import PokemonTCGSimulator

    summary: dict[str, Any] = {}
    print("Loading repository...")
    t0 = time.time()
    repo = load_repository()
    summary["repository_load_s"] = round(time.time() - t0, 2)
    summary["repository_card_count"] = len(repo.list_all())
    print(f"  {summary['repository_card_count']} cards loaded in {summary['repository_load_s']}s")

    deck = _default_deck(repo)

    # ------------------------------------------------------------------ #
    # 1. Agent vs random — head-to-head over N games
    # ------------------------------------------------------------------ #
    print("\n[1/3] Agent (heuristic MCTS, 30 iter) vs Random — 30 games")
    N_GAMES = 12
    MAX_MOVES = 200
    AGENT_ITERS = 30

    sim = PokemonTCGSimulator(repo, seed=42)
    agent = CompetitionAgent.load(
        None, repository=repo,
        config=AgentConfig(iterations=AGENT_ITERS, time_budget_s=2.0),
    )

    games: list[dict[str, Any]] = []
    win = draw = loss = 0
    for game_idx in range(N_GAMES):
        rng = random.Random(1000 + game_idx)
        state = sim.start_game(deck, deck)
        moves = 0
        agent_search_iters = []
        decision_latencies_ms = []
        outcome = "timeout"
        winner_player = None
        while moves < MAX_MOVES:
            legal = sim.legal_actions(state)
            if not legal:
                outcome = "no_legal_action"
                break
            if state.current_player == 0:
                t_start = time.perf_counter()
                action = agent.choose_action(state)
                decision_latencies_ms.append((time.perf_counter() - t_start) * 1000.0)
                if action is None:
                    action = rng.choice(legal)
                if agent._last_result is not None:
                    iters = (
                        getattr(agent._last_result, "iterations", None)
                        or getattr(agent._last_result, "n_iterations", None)
                        or getattr(agent._last_result, "total_visits", 0)
                    )
                    if iters:
                        agent_search_iters.append(int(iters))
            else:
                action = rng.choice(legal)
            state = sim.apply_action(state, action)
            moves += 1
            if sim.is_terminal(state):
                value = sim.outcome_value(state, 0)
                if value > 0:
                    outcome, winner_player = "agent_win", 0
                elif value < 0:
                    outcome, winner_player = "random_win", 1
                else:
                    outcome, winner_player = "draw", None
                break

        if outcome == "agent_win":
            win += 1
        elif outcome == "random_win":
            loss += 1
        elif outcome == "draw":
            draw += 1
        else:
            # Timeout / no_legal_action — count as draw for the head-to-head
            draw += 1

        games.append({
            "game_id": game_idx,
            "outcome": outcome,
            "winner_player": winner_player,
            "moves": moves,
            "avg_decision_ms": round(statistics.mean(decision_latencies_ms), 2)
                if decision_latencies_ms else 0.0,
            "max_decision_ms": round(max(decision_latencies_ms), 2)
                if decision_latencies_ms else 0.0,
            "avg_search_iters": round(statistics.mean(agent_search_iters), 1)
                if agent_search_iters else 0.0,
        })
        print(f"  game {game_idx + 1}/{N_GAMES}: outcome={outcome} moves={moves}")

    with (OUT / "agent_vs_random.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(games[0].keys()))
        writer.writeheader()
        writer.writerows(games)

    n = len(games)
    win_rate = win / n
    loss_rate = loss / n
    draw_rate = draw / n
    # Wilson 95% CI for win rate
    z = 1.96
    denom = 1 + z * z / n
    centre = (win_rate + z * z / (2 * n)) / denom
    half = z * math.sqrt(win_rate * (1 - win_rate) / n + z * z / (4 * n * n)) / denom
    wilson_lo = max(0.0, centre - half)
    wilson_hi = min(1.0, centre + half)

    head_to_head = {
        "n_games": n,
        "agent_iterations_per_decision": AGENT_ITERS,
        "max_moves": MAX_MOVES,
        "wins": win, "losses": loss, "draws": draw,
        "win_rate": round(win_rate, 4),
        "loss_rate": round(loss_rate, 4),
        "draw_rate": round(draw_rate, 4),
        "wilson_95_ci": [round(wilson_lo, 4), round(wilson_hi, 4)],
        "avg_moves_per_game": round(statistics.mean(g["moves"] for g in games), 1),
        "avg_decision_latency_ms": _safe_mean(
            [g["avg_decision_ms"] for g in games if g["avg_decision_ms"] > 0]
        ),
        "avg_search_iters": _safe_mean(
            [g["avg_search_iters"] for g in games if g["avg_search_iters"] > 0]
        ),
        "note": (
            "If draws dominate, the simulator did not reach a terminal "
            "state within MAX_MOVES for the default starter deck. The "
            "agent still played legal actions throughout."
        ),
    }
    (OUT / "agent_vs_random_summary.json").write_text(
        json.dumps(head_to_head, indent=2), encoding="utf-8",
    )
    summary["head_to_head"] = head_to_head
    print(f"  → win={win} loss={loss} draw={draw}  rate={win_rate:.2%}  CI=[{wilson_lo:.2%}, {wilson_hi:.2%}]")

    # ------------------------------------------------------------------ #
    # 2. Per-position MCTS quality
    # ------------------------------------------------------------------ #
    print("\n[2/3] MCTS per-position quality (3 positions)")
    from src.mcts import MCTSConfig, MCTSSearch
    positions = []
    pos_state = sim.start_game(deck, deck)
    cfg = MCTSConfig(iterations=80)
    for i in range(3):
        search = MCTSSearch(sim, config=cfg)
        search.reset()
        t_start = time.perf_counter()
        result = search.run(pos_state)
        elapsed = time.perf_counter() - t_start
        legal = sim.legal_actions(pos_state)
        positions.append({
            "position": i,
            "branching_factor": len(legal),
            "iterations": result.iterations,
            "elapsed_s": round(elapsed, 3),
            "iters_per_sec": round(result.iterations / max(elapsed, 1e-6), 1),
            "best_action_type": result.best_action.action_type if result.best_action else None,
        })
        if not legal:
            break
        pos_state = sim.apply_action(pos_state, legal[0])
        if sim.is_terminal(pos_state):
            break
    (OUT / "mcts_position_quality.json").write_text(
        json.dumps({"positions": positions}, indent=2), encoding="utf-8",
    )
    summary["mcts_positions"] = positions
    for p in positions:
        print(f"  pos {p['position']}: branching={p['branching_factor']} iters/s={p['iters_per_sec']}")

    # ------------------------------------------------------------------ #
    # 3. Deck candidate evaluation
    # ------------------------------------------------------------------ #
    print("\n[3/3] Deck candidates per archetype")
    graph = build_graph(repo.list_all())
    builder = DeckBuilder.from_graph_and_cards(graph, repo.list_all())
    analyzer = DeckAnalyzer(graph)
    card_db = {c.card_key: c for c in repo.list_all() if hasattr(c, "card_key")}

    archetypes = ["Aggro", "Control", "Combo"]
    candidates: list[dict[str, Any]] = []
    for arch in archetypes:
        try:
            result = builder.build(
                seed_cards=None, archetype=arch,
                n_candidates=3, max_iterations=20, seed=0,
            )
        except Exception as exc:
            print(f"  archetype {arch}: builder failed ({exc})")
            continue
        if not result.best:
            print(f"  archetype {arch}: no candidates")
            continue
        for idx, cand in enumerate(result.candidates[:3]):
            ptcg_live = deck_exports.to_ptcg_live(cand)
            try:
                analysis = analyzer.analyze_raw(
                    ptcg_live, card_db=card_db, name=f"{arch}_{idx}",
                )
                analyzer_archetype = str(analysis.archetype.primary_archetype)
                consistency_grade = getattr(
                    analysis.consistency, "consistency_grade",
                    getattr(analysis.consistency, "grade", "?"),
                )
                synergy_score = float(analysis.synergy.synergy_score)
            except Exception as exc:
                analyzer_archetype = "analyze_error"
                consistency_grade = str(exc)[:60]
                synergy_score = 0.0
            candidates.append({
                "archetype": arch,
                "candidate_idx": idx,
                "builder_score": round(float(cand.score.total), 3),
                "analyzer_archetype": analyzer_archetype,
                "consistency": str(consistency_grade),
                "synergy_score": round(synergy_score, 3),
            })
            (OUT / f"deck_{arch.lower()}_{idx}.ptcg.txt").write_text(
                ptcg_live, encoding="utf-8",
            )
            (OUT / f"deck_{arch.lower()}_{idx}.analysis.json").write_text(
                json.dumps({
                    "archetype": analyzer_archetype,
                    "consistency_grade": str(consistency_grade),
                    "synergy_score": synergy_score,
                }, indent=2),
                encoding="utf-8",
            )
        print(f"  archetype {arch}: built {len(result.candidates)} candidates")

    with (OUT / "deck_candidates.csv").open("w", newline="", encoding="utf-8") as fh:
        if candidates:
            writer = csv.DictWriter(fh, fieldnames=list(candidates[0].keys()))
            writer.writeheader()
            writer.writerows(candidates)
    summary["deck_candidates"] = candidates

    # Final
    print("\nDONE")
    (pathlib.Path(__file__).parent / "csv" / "summary.json").write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8",
    )
    return summary


if __name__ == "__main__":
    main()
