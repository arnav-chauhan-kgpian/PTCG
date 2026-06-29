"""
Competition runner — pure inference adapter for tournament submission.

Public API::

    from src.competition import CompetitionAgent

    agent = CompetitionAgent.load("checkpoint.pt")
    action = agent.choose_action(game_state)
"""

from src.competition.action_adapter import ActionAdapter
from src.competition.agent import CompetitionAgent
from src.competition.checkpoint_loader import CheckpointLoader
from src.competition.game_adapter import GameAdapter
from src.competition.inference_engine import InferenceEngine

__all__ = [
    "CompetitionAgent",
    "CheckpointLoader",
    "InferenceEngine",
    "ActionAdapter",
    "GameAdapter",
]
