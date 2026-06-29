"""
Reproducible benchmark runner.

Run from project root::

    python benchmarks/run.py                      # human-readable
    python benchmarks/run.py --json               # machine-readable
    python benchmarks/run.py --output bench.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time

from loguru import logger


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pokémon TCG AI benchmarks")
    parser.add_argument("--json", action="store_true",
                         help="Emit JSON instead of human-readable text")
    parser.add_argument("--output", default=None,
                         help="Write JSON output to this file")
    parser.add_argument("--actions", type=int, default=2000)
    parser.add_argument("--games", type=int, default=5)
    parser.add_argument("--encoder", type=int, default=500)
    parser.add_argument("--mcts-iters", type=int, default=200)
    args = parser.parse_args(argv)

    logger.remove()
    t0 = time.perf_counter()
    from src.cards import load_repository
    from src.evaluation import run_all_benchmarks

    repo = load_repository()
    report = run_all_benchmarks(
        repo,
        n_simulator_actions=args.actions,
        n_simulator_games=args.games,
        n_encoder=args.encoder,
        n_mcts_iters=args.mcts_iters,
    )
    elapsed = time.perf_counter() - t0
    payload = {
        "wall_clock_s": round(elapsed, 2),
        **report.to_dict(),
    }
    if args.output:
        import pathlib
        pathlib.Path(args.output).write_text(
            json.dumps(payload, indent=2), encoding="utf-8",
        )
    if args.json or args.output:
        print(json.dumps(payload, indent=2))
    else:
        for k, v in payload.items():
            print(f"  {k:<35}  {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
