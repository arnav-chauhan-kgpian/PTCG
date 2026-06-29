# Contributing

## Setup

```bash
pip install -e ".[dev]"
pre-commit install
```

## Code Style

- **Formatter**: Black (line length 100)
- **Linter**: Ruff
- **Type checker**: MyPy (strict mode)
- **Python**: 3.12+

All checks run automatically on commit via pre-commit hooks.

## Testing

```bash
pytest                         # all tests
pytest tests/cards/            # card layer only
pytest --cov=src               # with coverage
```

## Module Boundaries

Each phase has strict scope. Do not add cross-phase imports until the phase
is explicitly approved.

| Phase | Module | Scope |
|-------|--------|-------|
| 2 | `src/cards/` | Card data models, parser, repository, search |
| 3+ | `src/simulator/` | Game engine — no AI |
| 4+ | `src/rl/` | Reinforcement learning |
| 4+ | `src/search/` | MCTS |
| 5+ | `src/models/` | Neural networks |

## Commit Convention

```
feat(cards): add fuzzy search to CardRepository
fix(parser): handle empty expansion codes
test(normalizer): add edge cases for Dragon type
docs(readme): update quick-start example
```
