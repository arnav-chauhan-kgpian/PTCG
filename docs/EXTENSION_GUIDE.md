# Extension Guide

How to extend the framework without breaking existing contracts.

## Adding a new trainer card

1. Pick the printed card name; add a handler in `src/simulator/trainers.py`.
2. Register the handler in `_HANDLERS` keyed by name.
3. Add a regression test in `tests/simulator/test_p1_fixes.py` exercising
   the new card on a small synthetic decklist.

## Adding a new ability

1. Add a handler in `src/simulator/abilities.py`.
2. Register in `_HANDLERS`.
3. Add a regression test.

## Adding a new tool effect

1. Add the damage / HP / retreat delta to the dictionaries in
   `src/simulator/modifiers.py`.
2. Re-run the regression tests.

## Adding a new stadium effect

1. If the effect is binary (suppression, retreat reduction, type damage
   bonus), add a predicate to `src/simulator/modifiers.py`.
2. Consult it from the relevant simulator path (`legal_actions`,
   `compute_damage`, or `_h_use_ability`).
3. Add a regression test.

## Adding a new MCTS search strategy

1. Implement the strategy in `src/mcts/search.py` as a `Scorer` callable.
2. Register it in the `STRATEGIES` dict.
3. Document the new option in `MCTSConfig`.

## Adding a new neural architecture

1. Implement an `nn.Module` in `src/mcts/network.py` (or a new file).
2. Plug it into `NetworkWrapper` via a custom `model` parameter.
3. Use the existing `NeuralEvaluator` and `NeuralPriorPolicy` — the API
   is unchanged.

## Adding a new evaluation tool

1. Add the module under `src/evaluation/`.
2. Re-export from `src/evaluation/__init__.py`.
3. Hook it into the dashboard (`src/evaluation/dashboard.py`).
4. Add CLI entry-point if it's runnable from the command line.

## Adding a new REST endpoint

1. Add the route to `src/server/app.py`.
2. Define request/response Pydantic models inline.
3. Add a smoke test using `fastapi.testclient.TestClient`.

## Adding a new CLI command

1. Add a `_cmd_<name>` function in `src/cli/main.py`.
2. Register it in the `COMMANDS` dict.
3. Add a subparser configuration to `main()`.

## Adding a new feature to the encoder

1. Append a new `FeatureGroup` to `src/game_state/features.py`.
2. Update the encoder in `src/game_state/encoder.py`.
3. Increment any constants if the total size changes.
4. Re-run the full feature-encoder tests.

## Extending CardInstance state

CardInstance is intentionally minimal.  Per-instance runtime state
should be added via the `effect_flags` tuple (key=value strings).  Use
`with_flag()` / `has_flag()` / `get_flag()` to manipulate.

For first-class fields, you must extend the Pydantic frozen model AND
update `state_fingerprint` in `src/game_state/hashing.py`.

## Adding a new validation check

1. Add a check function in `src/validation/state_validator.py`.
2. Emit a `StateIssue` from `StateValidator.validate`.
3. Add a regression test.

## Coding conventions

- Pydantic v2 frozen models for immutable state.
- `dataclass(frozen=True)` for read-only value objects.
- Protocols (PEP-544) for plug-in interfaces — no inheritance required.
- Public modules expose a small `__all__`.
- All new modules carry at least a smoke test.
- Ruff and Black must pass: `ruff check src tests`.
