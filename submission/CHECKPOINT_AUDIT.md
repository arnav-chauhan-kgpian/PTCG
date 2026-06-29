# CHECKPOINT_AUDIT.md

## Scope

Search the entire repository for model checkpoints suitable for inference.

## Method

```bash
find . -name "*.pt"    -not -path "./venv/*" -not -path "./.git/*"
find . -name "*.ckpt"  -not -path "./venv/*" -not -path "./.git/*"
find . -name "*.safetensors" -not -path "./venv/*"
find . -type d -name "checkpoints"
```

## Findings

| Pattern | Result |
|---|---|
| `*.pt` | **0 files** |
| `*.ckpt` | **0 files** |
| `*.safetensors` | 0 files |
| `checkpoints/` directory | does not exist |

**No trained, partially-trained, or stub checkpoints exist anywhere in the repository.**

This is not fabricated. There is nothing to evaluate, rank, or pick. The repository has only ever produced inference outputs from a freshly-initialised network or from the heuristic evaluator.

## What this means for the submission

The competition agent (`src/competition/agent.py`) gracefully handles the no-checkpoint case:

- `CheckpointLoader.load(path=None)` returns a freshly-initialised `NetworkWrapper` (random weights) with `source="fresh"`.
- If PyTorch is not importable, `CompetitionAgent.load()` returns an agent with `inference=None`, falling back to `HeuristicEvaluator`.

Either path produces a working agent. Neither path produces a trained policy.

See `MODEL_SELECTION.md` for the chosen path and its measured implications.

## Reproducibility note

If a trained checkpoint is ever produced, the loader will validate it with three guarantees from the production-hardening pass:

1. **File existence check** — `FileNotFoundError` with a clean message.
2. **Suffix check** — refuses anything other than `.pt`.
3. **`weights_only=True`** — safe deserialisation, no RCE class.

These are enforced in `src/mcts/checkpoints.py:145` and `src/mcts/network.py:206`. Regression tests live in `tests/server/test_server.py::TestCheckpointSafety`.
