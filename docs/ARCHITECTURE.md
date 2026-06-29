# Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Card Knowledge Layer                            │
│   src/cards/                                                            │
│     parser → repository → effect engine → relationship graph            │
└────────────────────────────┬────────────────────────────────────────────┘
                             │ AnyCard, CardRepository, CardGraph
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       Deck Layer                                        │
│   src/decks/        deck analysis, archetype, synergy, win conditions   │
│   src/deck_builder/ programmatic 60-card deck construction              │
└────────────────────────────┬────────────────────────────────────────────┘
                             │ Deck, DeckReport, BuildResult
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                  Game State Representation                              │
│   src/game_state/                                                       │
│     GameState (immutable Pydantic) ─ PlayerState ─ CardInstance         │
│     FeatureEncoder → 741-dim flat vector + grouped slices               │
│     ActionMask + hashing + serialization + validators                   │
└────────────────────────────┬────────────────────────────────────────────┘
                             │ GameState, EncodedFeatures, ActionMask
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        MCTS Engine                                      │
│   src/mcts/                                                             │
│     MCTSSearch (selection → expansion → eval → backprop)                │
│       SimulatorProtocol  ──▶ injected (NullSimulator for tests)         │
│       EvaluatorProtocol  ──▶ Heuristic | Neural                         │
│       PriorPolicy        ──▶ Uniform | Heuristic | Neural               │
│       RolloutBase        ──▶ Heuristic | Random | Greedy | DepthLimited │
│       TranspositionTable (LRU, SHA-256 keyed)                           │
│       NetworkWrapper + InferenceCache + JointNetwork                    │
│       SelfPlayEngine → SelfPlayGame → TrainingSamples → ReplayBuffer    │
│       CheckpointManager + CheckpointMetadata                            │
└────────────────────────────┬────────────────────────────────────────────┘
                             │ Network, ReplayBuffer, SearchResult
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                Training Pipeline (AlphaZero loop)                       │
│   src/training/                                                         │
│     TrainingPipeline orchestrates per round:                            │
│         self-play → train → arena → promote → checkpoint                │
│     Trainer (supervised SGD/Adam/AdamW)                                 │
│     AlphaZeroLoss (policy CE + value MSE/BCE + entropy + L2)            │
│     Arena (head-to-head, alternating sides)                             │
│     PromotionPolicy (≥55% gate, customisable)                           │
│     ExperimentManager + PipelineCheckpoint (full resume)                │
│     MetricLogger (CSV / JSONL / Console / TensorBoard)                  │
│     Callbacks, EarlyStopping, Curriculum                                │
└─────────────────────────────────────────────────────────────────────────┘
```

## Extension points

| Where | What you customise | How |
|---|---|---|
| Simulator | Game rules / legal actions | Implement `mcts.SimulatorProtocol` |
| Evaluator | Value estimation | Implement `mcts.EvaluatorProtocol` |
| Prior policy | Action priors | Implement `mcts.PriorPolicy` |
| Rollout | Leaf evaluation strategy | Implement `mcts.RolloutBase` |
| Feature encoder | State → vector | Implement `mcts.FeatureEncoderProtocol` |
| Promotion gate | Accept candidate? | Pass `decide_fn` to `PromotionPolicy` |
| Curriculum | Initial state per round | Add `CurriculumStage` builders |
| Callbacks | Side-effects per phase | Subclass `BaseCallback` |
| Logging | New sinks | Add to `MetricLogger._sinks` |

## Design decisions

- **Immutable state.** `GameState`, `CardInstance`, `PlayerState`, and `Deck` are
  Pydantic frozen models so MCTS can copy-on-write freely. Hashing uses SHA-256
  over a canonical dict, so structurally identical states collide in the
  transposition table regardless of object identity.
- **Protocol-based simulator interface.** MCTS never imports game rules. Phase
  10's `TrainingPipeline` accepts any `SimulatorProtocol` implementation.
- **Two-tier scoring** in the deck builder: cheap `fast_score` (pure arithmetic
  on metrics) for the search inner loop, expensive `score_deck_full`
  (`DeckAnalyzer` + objective set) only for the final candidates.
- **Shared inference cache.** `NeuralEvaluator` and `NeuralPriorPolicy` share
  the same `InferenceCache` so one state = one forward pass.
- **Optional PyTorch.** All non-neural code (parser, deck builder, MCTS core,
  feature encoder, replay buffer, training targets, experiment manager) runs
  without `torch` installed. Neural components import lazily and raise a clear
  `ImportError` if torch is missing.
- **Restartable training.** Every round writes both a `NetworkWrapper`
  checkpoint and a `PipelineCheckpoint` so the loop can be resumed without
  metric drift.
- **No global state in the hot path.** Every component takes its RNG / cache /
  config via the constructor — no module-level mutability.

## Feature vector layout (741 dims)

| Group | Size | Description |
|---|---:|---|
| `active_self` | 28 | Current player's active Pokémon (HP, energy ×11, conditions ×5, retreat, flags, stage one-hot) |
| `bench_self` | 140 | 5 bench slots × 28 |
| `hand_self` | 7 | Counts + category fractions |
| `deck_self` | 2 | Size, ratio |
| `prizes_self` | 2 | Remaining, ratio |
| `discard_self` | 2 | Count, ratio |
| `lost_zone_self` | 1 | Count |
| `active_opp` … `lost_zone_opp` | 176 | Opponent's mirror (hand count only — hidden) |
| `stadium` | 1 | Present flag |
| `turn` | 4 | Turn / current-player / supporter-played / energy-attached |
| `history` | 250 | Last 10 actions × (24 action-type one-hot + player bit) |
| `embeddings` | 128 | Placeholder for future learned card embeddings (currently zero) |
| **Total** | **741** | |

## Reproducibility

| Concern | Mechanism |
|---|---|
| RNG seeds | Every component accepts `seed=...`; `SearchConfig`, `SelfPlayConfig`, `ArenaConfig`, `PipelineConfig` all expose seeds |
| Determinism | Network in `eval()` + `no_grad()` for inference; `state_fingerprint` is order-independent |
| Configuration snapshot | `PipelineConfig.to_dict()` captured in `ExperimentManifest.config_snapshot` |
| Git provenance | `CheckpointMetadata` and `ExperimentManifest` capture `git rev-parse HEAD` |
| Checkpoint compatibility | `validate_checkpoint(metadata, expected_config)` flags `input_size` / `action_size` mismatches |
| Replay compatibility | `validate_replay_buffer(buffer, feature_size, policy_size)` flags shape drift |
