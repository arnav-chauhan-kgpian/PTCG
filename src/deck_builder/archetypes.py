"""
Archetype templates — structural targets that guide deck construction.

Templates are NOT hardcoded decklists.  They specify target counts and
ratios that the ConstructiveGenerator tries to satisfy.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ArchetypeTemplate:
    name: str
    target_pokemon: int
    target_trainers: int
    target_energy: int
    prefer_basics: bool
    prefer_stage2: bool
    target_draw: int       # minimum draw cards
    target_search: int
    target_disruption: int
    target_recovery: int
    target_switching: int
    energy_count_range: tuple[int, int]  # (min, max)
    description: str


TEMPLATES: dict[str, ArchetypeTemplate] = {
    "Aggro": ArchetypeTemplate(
        name="Aggro",
        target_pokemon=16, target_trainers=32, target_energy=12,
        prefer_basics=True, prefer_stage2=False,
        target_draw=12, target_search=8, target_disruption=2,
        target_recovery=2, target_switching=4,
        energy_count_range=(10, 14),
        description="Fast attacks, single-prize basics, minimal setup.",
    ),
    "Control": ArchetypeTemplate(
        name="Control",
        target_pokemon=12, target_trainers=36, target_energy=12,
        prefer_basics=True, prefer_stage2=False,
        target_draw=14, target_search=10, target_disruption=10,
        target_recovery=6, target_switching=4,
        energy_count_range=(10, 14),
        description="Disruption-heavy, supporter-intensive, outlast opponent.",
    ),
    "Combo": ArchetypeTemplate(
        name="Combo",
        target_pokemon=18, target_trainers=34, target_energy=8,
        prefer_basics=False, prefer_stage2=True,
        target_draw=16, target_search=12, target_disruption=2,
        target_recovery=4, target_switching=2,
        energy_count_range=(6, 12),
        description="Stage 2 engines, high draw/search, explosive turns.",
    ),
    "Midrange": ArchetypeTemplate(
        name="Midrange",
        target_pokemon=18, target_trainers=28, target_energy=14,
        prefer_basics=False, prefer_stage2=False,
        target_draw=12, target_search=8, target_disruption=4,
        target_recovery=4, target_switching=4,
        energy_count_range=(12, 16),
        description="Balanced approach with Stage 1 attackers.",
    ),
    "Energy Ramp": ArchetypeTemplate(
        name="Energy Ramp",
        target_pokemon=16, target_trainers=24, target_energy=20,
        prefer_basics=False, prefer_stage2=False,
        target_draw=10, target_search=8, target_disruption=2,
        target_recovery=2, target_switching=2,
        energy_count_range=(18, 24),
        description="High energy counts, acceleration, massive attacks.",
    ),
    "Stall": ArchetypeTemplate(
        name="Stall",
        target_pokemon=10, target_trainers=38, target_energy=12,
        prefer_basics=True, prefer_stage2=False,
        target_draw=10, target_search=8, target_disruption=8,
        target_recovery=8, target_switching=6,
        energy_count_range=(8, 14),
        description="Healing, switching, and recycling to outlast opponent.",
    ),
    "Toolbox": ArchetypeTemplate(
        name="Toolbox",
        target_pokemon=20, target_trainers=28, target_energy=12,
        prefer_basics=True, prefer_stage2=False,
        target_draw=10, target_search=12, target_disruption=4,
        target_recovery=4, target_switching=4,
        energy_count_range=(10, 14),
        description="Diverse Pokémon, heavy search to find situational answers.",
    ),
    "Mill": ArchetypeTemplate(
        name="Mill",
        target_pokemon=8, target_trainers=40, target_energy=12,
        prefer_basics=True, prefer_stage2=False,
        target_draw=10, target_search=10, target_disruption=12,
        target_recovery=6, target_switching=2,
        energy_count_range=(8, 14),
        description="Deck-out opponent via heavy disruption and minimal attackers.",
    ),
}


def get_template(archetype: str) -> ArchetypeTemplate | None:
    return TEMPLATES.get(archetype)


def all_archetypes() -> list[str]:
    return list(TEMPLATES.keys())
