"""
Validation & Competitive Evaluation Phase (P2).

Pure evaluation tooling — no modifications to MCTS, simulator, neural,
or training APIs.  Every module here observes the existing engines and
produces measurable, exportable reports.

Public surfaces
---------------
- ``simulator_validation.validate_simulator(...)``  → ``SimulatorValidationReport``
- ``mcts_evaluation.evaluate_mcts(...)``             → ``MCTSEvaluationReport``
- ``selfplay_analytics.analyze_games(...)``          → ``SelfPlayAnalyticsReport``
- ``elo_arena.EloLeague``                            → round-robin tournaments
- ``opening_book.analyze_openings(...)``             → ``OpeningBookReport``
- ``explainability.explain_decision(...)``           → ``DecisionExplanation``
- ``benchmarks.run_all_benchmarks(...)``             → ``BenchmarkReport``
- ``dashboard.render_dashboard(...)``                → JSON / Markdown text
"""

from src.evaluation.benchmarks import BenchmarkReport, run_all_benchmarks
from src.evaluation.dashboard import render_dashboard, render_dashboard_markdown
from src.evaluation.elo_arena import EloLeague, EloRating
from src.evaluation.explainability import DecisionExplanation, explain_decision
from src.evaluation.mcts_evaluation import MCTSEvaluationReport, evaluate_mcts
from src.evaluation.opening_book import OpeningBookReport, analyze_openings
from src.evaluation.selfplay_analytics import (
    SelfPlayAnalyticsReport,
    analyze_games,
    record_game,
)
from src.evaluation.simulator_validation import (
    SimulatorValidationReport,
    validate_simulator,
)

__all__ = [
    "SimulatorValidationReport", "validate_simulator",
    "MCTSEvaluationReport", "evaluate_mcts",
    "SelfPlayAnalyticsReport", "analyze_games", "record_game",
    "EloLeague", "EloRating",
    "OpeningBookReport", "analyze_openings",
    "DecisionExplanation", "explain_decision",
    "BenchmarkReport", "run_all_benchmarks",
    "render_dashboard", "render_dashboard_markdown",
]
