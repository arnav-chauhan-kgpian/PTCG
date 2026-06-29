"""Smoke tests for the pokemon-ai CLI."""

from __future__ import annotations

from src.cli.main import main


class TestCLI:
    def test_no_args_prints_help(self, capsys):
        rc = main([])
        assert rc == 0
        captured = capsys.readouterr()
        assert "pokemon-ai" in captured.out

    def test_benchmark_runs(self, capsys):
        rc = main(["--json", "benchmark"])
        assert rc == 0

    def test_tournament_runs(self, capsys):
        rc = main(["--json", "tournament", "--rounds", "1"])
        assert rc == 0
