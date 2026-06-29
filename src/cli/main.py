"""
pokemon-ai CLI

Commands::

    pokemon-ai play          --checkpoint <path>      run an interactive game
    pokemon-ai train         --config <path>          run a training round
    pokemon-ai evaluate      --games <n>              self-play analytics
    pokemon-ai benchmark                              run benchmark suite
    pokemon-ai build-deck    --seed <name>            build a 60-card deck
    pokemon-ai analyze-deck  <decklist>               run DeckAnalyzer
    pokemon-ai validate      --games <n>              SimulatorValidator
    pokemon-ai tournament    --rounds <n>             Elo round-robin
    pokemon-ai infer         --checkpoint <path>      one-shot move on stdin
    pokemon-ai serve         --host 0.0.0.0 --port 8000   FastAPI server

All commands accept ``--json`` to emit machine-readable output.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="pokemon-ai",
        description="Pokémon TCG AI competition framework",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Emit machine-readable JSON output where applicable",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("play", help="Interactive game (smoke run)").add_argument(
        "--checkpoint", default=None,
    )
    train_p = sub.add_parser("train", help="Run one training round")
    train_p.add_argument("--rounds", type=int, default=1)

    eval_p = sub.add_parser("evaluate", help="Self-play analytics")
    eval_p.add_argument("--games", type=int, default=5)
    eval_p.add_argument("--max-moves", type=int, default=200)

    sub.add_parser("benchmark", help="Run benchmark suite")
    bd = sub.add_parser("build-deck", help="Build a 60-card deck")
    bd.add_argument("--seed", default=None)
    bd.add_argument("--archetype", default=None)

    ad = sub.add_parser("analyze-deck", help="Analyse a deck list")
    ad.add_argument("decklist", help="Path to text decklist")

    val = sub.add_parser("validate", help="Run SimulatorValidator")
    val.add_argument("--games", type=int, default=5)

    tour = sub.add_parser("tournament", help="Run an Elo round-robin")
    tour.add_argument("--rounds", type=int, default=3)

    inf = sub.add_parser("infer", help="Decide a move from stdin JSON state")
    inf.add_argument("--checkpoint", default=None)

    srv = sub.add_parser("serve", help="Run the FastAPI server")
    srv.add_argument("--host", default="0.0.0.0")
    srv.add_argument("--port", type=int, default=8000)
    srv.add_argument("--checkpoint", default=None)

    args = parser.parse_args(argv)
    cmd = args.command

    if cmd is None:
        parser.print_help()
        return 0

    handler = COMMANDS.get(cmd)
    if handler is None:
        parser.error(f"unknown command: {cmd}")
    try:
        result = handler(args)
    except KeyboardInterrupt:
        return 130
    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        print(_render_human(cmd, result))
    return 0


# -------------------------------------------------------------------------
# Command handlers
# -------------------------------------------------------------------------

def _cmd_play(args) -> dict[str, Any]:
    from src.cards import load_repository
    from src.competition.agent import AgentConfig, CompetitionAgent
    from src.evaluation.simulator_validation import _default_deck
    from src.simulator import PokemonTCGSimulator

    repo = load_repository()
    deck = _default_deck(repo)
    sim = PokemonTCGSimulator(repo, seed=0)
    state = sim.start_game(deck, deck)
    agent = CompetitionAgent.load(
        args.checkpoint, repository=repo,
        config=AgentConfig(iterations=20),
    )
    action = agent.choose_action(state)
    return {
        "action_type": action.action_type if action else None,
        "details": dict(action.details) if action else {},
        "agent": agent.summary(),
    }


def _cmd_train(args) -> dict[str, Any]:
    return {"status": "stub", "rounds": args.rounds,
             "message": "Full training requires a deck/action-map curriculum."}


def _cmd_evaluate(args) -> dict[str, Any]:
    from src.cards import load_repository
    from src.evaluation import analyze_games
    repo = load_repository()
    report = analyze_games(repo, n_games=args.games, max_moves=args.max_moves)
    return report.to_dict()


def _cmd_benchmark(args) -> dict[str, Any]:
    from src.cards import load_repository
    from src.evaluation import run_all_benchmarks
    repo = load_repository()
    report = run_all_benchmarks(
        repo, n_simulator_actions=500, n_simulator_games=2,
        n_encoder=100, n_mcts_iters=50,
    )
    return report.to_dict()


def _cmd_build_deck(args) -> dict[str, Any]:
    from src.cards import load_repository
    from src.cards.relationships import build_graph
    from src.deck_builder import DeckBuilder
    from src.deck_builder import exports as deck_exports
    repo = load_repository()
    graph = build_graph(repo.list_all())
    builder = DeckBuilder.from_graph_and_cards(graph, repo.list_all())
    result = builder.build(
        seed_cards=[args.seed] if args.seed else None,
        archetype=args.archetype,
        n_candidates=1, max_iterations=20, seed=0,
    )
    best = result.best
    if best is None:
        return {"error": "no candidates"}
    return {
        "ptcg_live": deck_exports.to_ptcg_live(best),
        "score": float(best.score.total),
    }


def _cmd_analyze_deck(args) -> dict[str, Any]:
    import pathlib

    from src.cards import load_repository
    from src.cards.relationships import build_graph
    from src.decks.analyzer import analyze_raw
    text = pathlib.Path(args.decklist).read_text(encoding="utf-8")
    repo = load_repository()
    build_graph(repo.list_all())
    report = analyze_raw(text, repo, name="CLI")
    return {
        "archetype": str(report.archetype.primary_archetype),
        "consistency": str(report.consistency.grade),
        "synergy_score": float(report.synergy.synergy_score),
    }


def _cmd_validate(args) -> dict[str, Any]:
    from src.cards import load_repository
    from src.validation import SimulatorValidator
    repo = load_repository()
    return SimulatorValidator(repo).run(n_games=args.games).to_dict()


def _cmd_tournament(args) -> dict[str, Any]:
    import random

    from src.evaluation import EloLeague
    league = EloLeague()
    for name in ("random_a", "random_b"):
        league.register(name)
    rng = random.Random(0)
    for _ in range(args.rounds * 2):
        league.record_result(
            "random_a", "random_b",
            float(rng.choice([0.0, 0.5, 1.0])),
        )
    return league.to_dict()


def _cmd_infer(args) -> dict[str, Any]:
    from src.competition.agent import AgentConfig, CompetitionAgent
    state_dict = json.loads(sys.stdin.read() or "{}")
    agent = CompetitionAgent.load(
        args.checkpoint, config=AgentConfig(iterations=30),
    )
    return agent.choose_action_dict(state_dict)


def _cmd_serve(args) -> dict[str, Any]:
    try:
        import uvicorn  # type: ignore[import-untyped]
    except ImportError:
        return {"error": "uvicorn not installed"}
    from src.server import create_app
    app = create_app(checkpoint_path=args.checkpoint)
    uvicorn.run(app, host=args.host, port=args.port)
    return {"status": "served"}


COMMANDS = {
    "play":         _cmd_play,
    "train":        _cmd_train,
    "evaluate":     _cmd_evaluate,
    "benchmark":    _cmd_benchmark,
    "build-deck":   _cmd_build_deck,
    "analyze-deck": _cmd_analyze_deck,
    "validate":     _cmd_validate,
    "tournament":   _cmd_tournament,
    "infer":        _cmd_infer,
    "serve":        _cmd_serve,
}


def _render_human(command: str, result: dict[str, Any]) -> str:
    lines = [f"--- {command} ---"]
    for k, v in result.items():
        lines.append(f"  {k}: {v}")
    return "\n".join(lines)
