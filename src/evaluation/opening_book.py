"""
P2.6 — Opening book evaluation.

Generates many opening positions from a fixed deck list, runs short MCTS
searches on each, and reports diversity / confidence / entropy statistics.
"""

from __future__ import annotations

import math
import random
from collections import Counter
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from src.mcts import MCTSConfig, MCTSSearch
from src.simulator import PokemonTCGSimulator

if TYPE_CHECKING:
    from src.cards.repository import CardRepository


@dataclass
class OpeningResult:
    seed: int
    chosen_action: str = ""
    branching_factor: int = 0
    entropy: float = 0.0
    top1_visit_share: float = 0.0


@dataclass
class OpeningBookReport:
    samples: list[OpeningResult] = field(default_factory=list)

    @property
    def diversity(self) -> int:
        return len({s.chosen_action for s in self.samples if s.chosen_action})

    @property
    def avg_entropy(self) -> float:
        if not self.samples:
            return 0.0
        return sum(s.entropy for s in self.samples) / len(self.samples)

    @property
    def avg_top1_share(self) -> float:
        if not self.samples:
            return 0.0
        return sum(s.top1_visit_share for s in self.samples) / len(self.samples)

    @property
    def avg_branching(self) -> float:
        if not self.samples:
            return 0.0
        return sum(s.branching_factor for s in self.samples) / len(self.samples)

    @property
    def unstable_openings(self) -> list[OpeningResult]:
        """Openings whose top action has under 50% visit share."""
        return [s for s in self.samples if s.top1_visit_share < 0.5]

    def to_dict(self) -> dict:
        chosen = Counter(s.chosen_action for s in self.samples if s.chosen_action)
        return {
            "n_samples": len(self.samples),
            "unique_chosen_actions": self.diversity,
            "avg_entropy": round(self.avg_entropy, 4),
            "avg_top1_share": round(self.avg_top1_share, 4),
            "avg_branching": round(self.avg_branching, 2),
            "unstable_openings": len(self.unstable_openings),
            "top_choices": dict(chosen.most_common(10)),
        }


def analyze_openings(
    repository: CardRepository,
    *,
    n_samples: int = 50,
    mcts_iterations: int = 30,
    deck: list[int] | None = None,
    seed: int = 0,
) -> OpeningBookReport:
    report = OpeningBookReport()
    base_rng = random.Random(seed)

    if deck is None:
        from src.evaluation.simulator_validation import _default_deck
        deck = _default_deck(repository)

    cfg = MCTSConfig(iterations=mcts_iterations, time_budget_s=10.0)
    for i in range(n_samples):
        sample_seed = base_rng.randint(0, 10_000)
        sim = PokemonTCGSimulator(repository, seed=sample_seed)
        state = sim.start_game(deck, deck)
        if state.players[0].active is None:
            continue
        result = MCTSSearch(sim, config=cfg).run(state)
        counts = list(result.visit_counts.values())
        total = sum(counts) or 1
        entropy = 0.0
        for c in counts:
            if c <= 0:
                continue
            p = c / total
            entropy -= p * math.log(p)
        top1 = max(counts) / total if counts else 0.0
        report.samples.append(OpeningResult(
            seed=sample_seed,
            chosen_action=str(result.best_action) if result.best_action else "",
            branching_factor=len(counts),
            entropy=round(entropy, 4),
            top1_visit_share=round(top1, 4),
        ))
    return report
