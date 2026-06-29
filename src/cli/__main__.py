"""Allow ``python -m src.cli`` and ``python -m pokemon_ai``."""

from src.cli.main import main

if __name__ == "__main__":
    raise SystemExit(main())
