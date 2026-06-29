"""
Pokémon TCG simulator — production rules engine.

Implements ``src.mcts.SimulatorProtocol`` so MCTS, SelfPlayEngine, Arena,
and TrainingPipeline all consume this module unchanged.

Quick start::

    from src.cards import load_repository
    from src.simulator import PokemonTCGSimulator

    repo = load_repository()
    sim = PokemonTCGSimulator(repo, seed=42)
    state = sim.start_game(deck_a, deck_b)
    while not sim.is_terminal(state):
        actions = sim.legal_actions(state)
        state = sim.apply_action(state, actions[0])
"""

from src.simulator import abilities, actions, effects, exports, modifiers, trainers, zones
from src.simulator.abilities import named_ability_handlers
from src.simulator.attack_engine import DamageResult, apply_damage, compute_damage, heal
from src.simulator.effects import (
    SIM_REPORT,
    SimulatorReport,
    UnsupportedEffectRecord,
    apply_ability_effects,
    apply_attack_effects,
    apply_effect,
    apply_trainer_effects,
)
from src.simulator.energy_engine import (
    attached_energy_provides,
    has_energy_for_cost,
    retreat_cost,
)
from src.simulator.evolution_engine import evolve_pokemon
from src.simulator.knockout import (
    detect_knockouts,
    process_all_knockouts,
    process_knockout,
)
from src.simulator.legal_actions import legal_actions
from src.simulator.prizes import take_prize
from src.simulator.randomizer import Randomizer
from src.simulator.rules import DEFAULT_RULES, GameRules
from src.simulator.setup import build_initial_state
from src.simulator.simulator import PokemonTCGSimulator
from src.simulator.trainers import named_trainer_handlers
from src.simulator.turn_manager import apply_between_turn_status, begin_turn, end_turn
from src.simulator.validators import LegalityResult, is_legal
from src.simulator.victory import apply_victory_check, check_victory

__all__ = [
    "PokemonTCGSimulator",
    "GameRules",
    "DEFAULT_RULES",
    "Randomizer",
    "build_initial_state",
    "legal_actions",
    "compute_damage",
    "apply_damage",
    "heal",
    "DamageResult",
    "attached_energy_provides",
    "has_energy_for_cost",
    "retreat_cost",
    "evolve_pokemon",
    "process_knockout",
    "process_all_knockouts",
    "detect_knockouts",
    "take_prize",
    "begin_turn",
    "end_turn",
    "apply_between_turn_status",
    "check_victory",
    "apply_victory_check",
    "is_legal",
    "LegalityResult",
    "actions",
    "zones",
    "effects",
    "exports",
    "trainers",
    "abilities",
    "modifiers",
    "named_trainer_handlers",
    "named_ability_handlers",
    # P0.5 / P0.6
    "SIM_REPORT",
    "SimulatorReport",
    "UnsupportedEffectRecord",
    "apply_effect",
    "apply_attack_effects",
    "apply_trainer_effects",
    "apply_ability_effects",
]
