# SUBMISSION_BASELINE.md

Independent verification of the repository state on **2026-06-29**.

## Repository identity

| | |
|---|---|
| Path | `D:\PTCG` |
| Git repo | **No** — `git rev-parse HEAD` returns *not a git repository*. No commit hash is available. |
| Working tree size | 174 backend Python files (28,889 LOC), 71 frontend TS/TSX files (5,003 LOC) |

## Runtime environment

| Tool | Version |
|---|---|
| Python | 3.12.10 (CPython, Windows 11) |
| Interpreter | `C:\Users\Dell\AppData\Local\Programs\Python\Python312\python.exe` |
| Platform | win32, AMD64 |

## Installed dependency versions (measured via `importlib.metadata`)

| Package | Version |
|---|---|
| pydantic | 2.13.4 |
| loguru | 0.7.3 |
| rich | 15.0.0 |
| hydra-core | 1.3.3 |
| rapidfuzz | 3.14.5 |
| networkx | 3.6.1 |
| fastapi | 0.138.1 |
| torch | 2.12.1+cpu |
| matplotlib | 3.10.0 |
| uvicorn | not registered in metadata, but importable |

## Build status

| Step | Command | Result |
|---|---|---|
| Lint | `ruff check src tests` | ✅ **All checks passed!** |
| Pytest | `python -m pytest -q` | ✅ All passed (last run: 1,072 / 1,072 collected, 4 conditional skips for missing CSV — pre-existing). |
| Benchmark | `python -m src.cli --json benchmark` | ✅ Runs to completion. JSON saved to `submission/benchmarks/benchmark_baseline.json`. |
| Simulator validation | `python -m src.cli --json evaluate --games 20` | ✅ Runs to completion. 1,600 actions executed, 0 illegal attempts, 0 repeated states. |
| Server import | `from src.server.app import create_app` | ✅ Returns FastAPI app with the 6 documented routes plus `/openapi.json`, `/docs`, `/redoc`. |
| Card load | `load_repository()` | ✅ 1,267 cards parsed and indexed in 0.15 s. |

## Benchmark summary (CPU baseline, measured)

| Metric | Value |
|---|---|
| Simulator actions / s | 1,378.3 |
| Simulator games / s | 6.60 |
| Encoder ops / s | 3,375.4 |
| Network single-state latency | 47.56 ms |
| Network batched throughput | 4,931.8 forwards / s |
| MCTS iterations / s | 161.0 |
| Replay buffer throughput | 498,241.4 samples / s |

Source: `submission/benchmarks/benchmark_baseline.json` produced by `pokemon-ai benchmark`.

## Checkpoint inventory

| | |
|---|---|
| `*.pt` under repo | **none found** |
| `*.ckpt` under repo | **none found** |
| `checkpoints/` directory | does not exist |
| Bundled weights in `pokemon_ai.egg-info` | none |

See `CHECKPOINT_AUDIT.md` for the full audit.

## Notes & known limitations

- The repository is not a git repository, so the writeup cannot include an immutable commit hash. The build is otherwise fully reproducible from the file tree at the timestamps above.
- `uvicorn` is importable but not registered in `importlib.metadata`. This does not affect serving — `pokemon-ai serve` works.
- The CSV card data (`EN_Card_Data.csv`) is required at runtime and lives at the repository root. The Docker image copies it explicitly.
