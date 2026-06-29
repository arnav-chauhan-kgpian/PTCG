# Pokémon TCG AI

[![CI](https://img.shields.io/badge/CI-passing-brightgreen.svg)](.github/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-1100%2B-brightgreen.svg)](tests/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

A production-grade AlphaZero-style framework for the Kaggle **Pokémon TCG AI
Battle Challenge** — card knowledge, deck intelligence, immutable game
state, simulator, MCTS with neural evaluation, self-play, training, and a
competition runner with REST API and CLI.

## Architecture

```
┌────────────────────────────────────────────────────────────────┐
│  Card Knowledge Layer                                          │
│    src/cards/        parser · effect engine · relationship graph│
└────────────────────────────┬───────────────────────────────────┘
                             │
┌────────────────────────────▼───────────────────────────────────┐
│  Deck Layer                                                    │
│    src/decks/        analysis · archetype · synergy            │
│    src/deck_builder/ programmatic 60-card construction         │
└────────────────────────────┬───────────────────────────────────┘
                             │
┌────────────────────────────▼───────────────────────────────────┐
│  Game State + Feature Encoder                                  │
│    src/game_state/   GameState · CardInstance · 741-dim encoder│
└────────────────────────────┬───────────────────────────────────┘
                             │
┌────────────────────────────▼───────────────────────────────────┐
│  Simulator (P0–P1 fidelity)                                    │
│    src/simulator/    rules engine · 17 trainers · 8 abilities  │
│                      · tools · stadiums · special energy        │
└────────────────────────────┬───────────────────────────────────┘
                             │
┌────────────────────────────▼───────────────────────────────────┐
│  MCTS + Neural Inference                                       │
│    src/mcts/         UCT · PUCT · transposition · neural eval  │
│                      InferenceCache · self-play · replay buffer │
└────────────────────────────┬───────────────────────────────────┘
                             │
┌────────────────────────────▼───────────────────────────────────┐
│  Training Pipeline                                             │
│    src/training/     trainer · arena · promotion · experiments │
└────────────────────────────┬───────────────────────────────────┘
                             │
┌────────────────────────────▼───────────────────────────────────┐
│  Evaluation & Validation                                       │
│    src/evaluation/   simulator validation · MCTS quality · Elo │
│    src/validation/   SimulatorValidator · ReplayValidator      │
└────────────────────────────┬───────────────────────────────────┘
                             │
┌────────────────────────────▼───────────────────────────────────┐
│  Competition Mode                                              │
│    src/competition/  CompetitionAgent · CheckpointLoader       │
│    src/server/       FastAPI REST surface                       │
│    src/cli/          pokemon-ai command-line entry             │
└────────────────────────────────────────────────────────────────┘
```

## Installation

```bash
# minimum (CPU only)
pip install -e .

# development + REST server
pip install -e ".[dev,server]"

# add PyTorch (CPU)
pip install torch --index-url https://download.pytorch.org/whl/cpu
```

## Quick Start

```python
from src.cards import load_repository
from src.simulator import PokemonTCGSimulator
from src.competition import CompetitionAgent

repo = load_repository()
sim = PokemonTCGSimulator(repo, seed=42)

agent = CompetitionAgent.load(checkpoint_path=None, repository=repo)
state = sim.start_game(deck_a=[...], deck_b=[...])
action = agent.choose_action(state)
print(action)
```

## Training

```python
from src.training import TrainingPipeline, PipelineConfig
pipeline = TrainingPipeline(simulator, action_map, PipelineConfig(rounds=100))
pipeline.run()
```

The pipeline runs self-play → train → arena → promotion → checkpoint with
resume support out of the box.

## Inference

```python
from src.competition import CompetitionAgent
agent = CompetitionAgent.load("checkpoint.pt")
action = agent.choose_action(state)
```

## Simulator

```python
from src.simulator import PokemonTCGSimulator
sim = PokemonTCGSimulator(repo, seed=42)
state = sim.start_game(deck_a, deck_b)
while not sim.is_terminal(state):
    actions = sim.legal_actions(state)
    state = sim.apply_action(state, actions[0])
```

| Subsystem | Status |
|---|---|
| Game loop / draw / KO / deckout | ✅ 100 % |
| Prize accounting | ✅ 100 % |
| Trainers fully supported | 🟢 ~79 % (151 / 191) |
| Attacks fully supported | 🟢 ~88 % (1,363 / 1,558) |
| Abilities fully supported | 🟢 ~78 % (171 / 218) |
| Special conditions | ✅ 100 % |
| Tools / Stadiums / Special Energy | 🟡 framework + 4 tools, 1 stadium, 1 sp-energy wired |

## Deck Builder

```python
from src.cards import load_repository
from src.cards.relationships import build_graph
from src.deck_builder import DeckBuilder

repo = load_repository()
graph = build_graph(repo.list_all())
builder = DeckBuilder.from_graph_and_cards(graph, repo.list_all())
result = builder.build(seed_cards=["Charizard ex"], n_candidates=3)
```

## MCTS

```python
from src.mcts import MCTSSearch, MCTSConfig
result = MCTSSearch(simulator, config=MCTSConfig(iterations=400)).run(state)
print(result.best_action, result.statistics.iterations_per_second)
```

## Competition Mode

```python
from src.competition import CompetitionAgent
agent = CompetitionAgent.load("checkpoint.pt")
move = agent.choose_action_dict(state_dict_from_organizer)
```

`CompetitionAgent` is pure inference — no training stack needed at runtime.

## REST API

```bash
pokemon-ai serve --host 0.0.0.0 --port 8000
```

| Method | Path | Description |
|---|---|---|
| `POST` | `/move` | Choose an action for a serialised GameState |
| `POST` | `/evaluate` | Win-probability estimate from the current perspective |
| `POST` | `/deck/analyze` | Run DeckAnalyzer on a deck list |
| `POST` | `/deck/build` | Build a 60-card deck via DeckBuilder |
| `GET`  | `/health` | Liveness probe |
| `GET`  | `/metrics` | Request counters + cache hit-rate |

OpenAPI / Swagger docs at `http://localhost:8000/docs`.

## CLI

```bash
pokemon-ai play                          # smoke run on a random opening
pokemon-ai evaluate --games 10           # self-play analytics (JSON with --json)
pokemon-ai benchmark                     # performance benchmarks
pokemon-ai build-deck --seed "Charizard ex"
pokemon-ai analyze-deck mydeck.txt
pokemon-ai validate --games 5            # SimulatorValidator
pokemon-ai tournament --rounds 3         # Elo round-robin
pokemon-ai infer --checkpoint model.pt   # JSON state on stdin → JSON action on stdout
pokemon-ai serve                          # FastAPI server (default port 8000)
```

Add `--json` to any command for machine-readable output.

## Benchmarks

Measured on the bundled 1,267-card repository (CPU, single process):

| Layer | Throughput |
|---|---|
| Simulator | ~5,500 actions/s · ~18 games/s |
| Feature encoder | ~6,400 encodes/s |
| Neural inference (64-hidden) | 916 µs single, ~7,900 states/s batched-32 |
| MCTS | ~241 iter/s on real card states |
| Replay buffer | ~1.1 M samples/s |

## Limitations

- **CopyAttack** and a handful of rare effect classes remain unsupported.
- Specific stadium / tool / special-energy effects beyond the core set
  (Path to the Peak, Defiance Band, Bravery Charm, Hero's Cape, Air
  Balloon, Counter Gain, Double Turbo Energy) are not yet wired —
  framework is in place via `src/simulator/modifiers.py`.
- The neural policy head currently assumes a fixed action map; per-game
  target choices are auto-resolved by the simulator.
- Coverage tracker reports observed gaps via `SIM_REPORT`.

## Developer Guide

- `pyproject.toml` — packaging, deps, optional extras (`dev`, `server`, `neural`).
- `.github/workflows/ci.yml` — full CI: lint, tests, benchmarks, docker.
- `docs/` — architecture diagrams + per-package design notes.
- `tests/` — pytest suite (1,100+ tests).
- `benchmarks/` — reproducible performance runs.
- `Dockerfile` + `docker-compose.yml` — production image.

Run the full audit with:

```bash
pytest --cov=src --cov-report=term
ruff check src tests
pokemon-ai benchmark
```

## Docker

```bash
docker build -t pokemon-ai:latest .
docker run --rm -p 8000:8000 pokemon-ai:latest
# → POST http://localhost:8000/move
```

## License

MIT — see [LICENSE](LICENSE).
