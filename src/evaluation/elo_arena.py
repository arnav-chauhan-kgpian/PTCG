"""
P2.5 — Elo league for self-play comparisons.

Wraps the existing ``training.Arena`` and adds:
  - round-robin tournaments
  - Elo updates per game
  - win-rate matrices
  - Glicko-ready (carries variance fields, not yet wired)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


@dataclass
class EloRating:
    """Elo rating with Glicko-style variance fields."""
    name: str
    rating: float = 1500.0
    rating_deviation: float = 350.0    # placeholder for Glicko-2
    volatility: float = 0.06            # placeholder for Glicko-2
    games_played: int = 0
    wins: int = 0
    losses: int = 0
    draws: int = 0

    @property
    def score(self) -> float:
        return self.wins + 0.5 * self.draws


@dataclass
class EloLeague:
    """Round-robin Elo league with per-pair win-rate matrix."""
    ratings: dict[str, EloRating] = field(default_factory=dict)
    k_factor: float = 32.0
    games: list[tuple[str, str, int]] = field(default_factory=list)  # (a, b, winner)
    # win_matrix[a][b] = wins of a against b
    win_matrix: dict[str, dict[str, int]] = field(default_factory=dict)

    def register(self, name: str, initial_rating: float = 1500.0) -> None:
        if name not in self.ratings:
            self.ratings[name] = EloRating(name=name, rating=initial_rating)
        self.win_matrix.setdefault(name, {})

    def record_result(self, player_a: str, player_b: str,
                       score_a: float) -> None:
        """Record one game outcome.  ``score_a`` is 1.0 win, 0.5 draw, 0.0 loss."""
        self.register(player_a)
        self.register(player_b)
        a = self.ratings[player_a]
        b = self.ratings[player_b]
        ea = 1.0 / (1.0 + 10.0 ** ((b.rating - a.rating) / 400.0))
        eb = 1.0 - ea
        a.rating += self.k_factor * (score_a - ea)
        b.rating += self.k_factor * ((1.0 - score_a) - eb)
        a.games_played += 1
        b.games_played += 1
        if score_a == 1.0:
            a.wins += 1
            b.losses += 1
            self.win_matrix[player_a][player_b] = (
                self.win_matrix[player_a].get(player_b, 0) + 1
            )
        elif score_a == 0.0:
            a.losses += 1
            b.wins += 1
            self.win_matrix[player_b][player_a] = (
                self.win_matrix[player_b].get(player_a, 0) + 1
            )
        else:
            a.draws += 1
            b.draws += 1
        self.games.append((
            player_a, player_b,
            1 if score_a == 1.0 else 0 if score_a == 0.0 else -1,
        ))

    def round_robin(
        self, play_fn, *, n_games_per_pair: int = 2,
    ) -> None:
        """Play a round-robin tournament; play_fn(a, b) → score_a per game."""
        names = list(self.ratings.keys())
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                for _ in range(n_games_per_pair):
                    score = play_fn(a, b)
                    self.record_result(a, b, score)

    def standings(self) -> list[EloRating]:
        return sorted(self.ratings.values(), key=lambda r: -r.rating)

    def win_rate_matrix(self) -> dict[str, dict[str, float]]:
        """Pairwise win-rate of row against column."""
        matrix: dict[str, dict[str, float]] = {}
        for a in self.ratings:
            matrix[a] = {}
            for b in self.ratings:
                if a == b:
                    matrix[a][b] = 0.5
                    continue
                wins_a = self.win_matrix.get(a, {}).get(b, 0)
                wins_b = self.win_matrix.get(b, {}).get(a, 0)
                games = wins_a + wins_b
                matrix[a][b] = wins_a / games if games else 0.5
        return matrix

    def to_dict(self) -> dict:
        return {
            "standings": [
                {"name": r.name, "rating": round(r.rating, 1),
                 "games": r.games_played, "wins": r.wins,
                 "losses": r.losses, "draws": r.draws,
                 "score": round(r.score, 1)}
                for r in self.standings()
            ],
            "win_rate_matrix": {
                a: {b: round(v, 3) for b, v in row.items()}
                for a, row in self.win_rate_matrix().items()
            },
            "total_games": len(self.games),
        }
