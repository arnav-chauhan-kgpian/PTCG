# Pipeline Diagrams

## End-to-end training pipeline

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Curriculum             builds initial GameStates                       │
└──────────────┬──────────────────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  SelfPlayEngine          MCTSSearch + NeuralEvaluator + NeuralPolicy    │
│                          → SelfPlayGame → TrainingSample                │
└──────────────┬──────────────────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  ReplayBuffer           FIFO capacity buffer (JSON-serialisable)        │
└──────────────┬──────────────────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Trainer                AlphaZeroLoss (policy CE + value MSE + entropy) │
│                          AMP / grad-clip / scheduler                    │
└──────────────┬──────────────────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Arena                  head-to-head candidate vs. best                 │
│  PromotionPolicy        gate: candidate score ≥ 0.55                    │
└──────────────┬──────────────────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  CheckpointManager      ckpt_NNNNNN.pt with metadata + git hash         │
│  PipelineCheckpoint     full resume snapshot                            │
└─────────────────────────────────────────────────────────────────────────┘
```

## Inference pipeline (competition mode)

```
state JSON ──► GameAdapter.from_dict ──► GameState
                                            │
                                            ▼
                                      MCTSSearch
                                       │       │
                              ┌────────▼─┐   ┌─▼────────┐
                              │ Neural    │  │ Heuristic │
                              │ Evaluator │  │ Evaluator │
                              │ +Cache    │  │           │
                              └────────┬──┘  └─┬─────────┘
                                       │       │
                                       ▼       ▼
                                   SearchResult
                                          │
                                          ▼
                                   ActionAdapter.to_dict
                                          │
                                          ▼
                                     action JSON
```

## Validation pipeline

```
SimulatorValidator(repository)
        │
        ├──► validate_simulator     random self-play correctness
        │
        ├──► measure_rule_coverage  trainer / attack / ability tally
        │
        └──► render_dashboard       Markdown + JSON snapshot
```
