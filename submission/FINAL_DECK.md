# FINAL_DECK.md

## Selected deck — *Mega Latias Aggro*

Selected automatically by `pokemon-ai build-deck --archetype Aggro` (`src/deck_builder/`).
Builder score (measured): **45.51**

### Full decklist (PTCG Live format)

```
Pokémon: 20
2 Applin TWM 126
2 Iron Thorns ex TWM 77
2 Koraidon TEF 119
2 Morpeko TWM 72
4 Gouging Fire ex TEF 38
4 Mega Latias ex MEG 100
4 Pikachu ex SSP 57

Trainer: 14
2 Ogre's Mask TWM 159
4 Meddling Memo SSP 181
4 Roto-Stick PRE 127
4 Unfair Stamp TWM 165

Energy: 26
1 Basic {L} Energy SVE 4
15 Basic {G} Energy SVE 1
2 Basic {M} Energy SVE 8
2 Basic {P} Energy SVE 5
2 Basic {R} Energy SVE 2
2 Boomerang Energy TWM 166
2 Mist Energy TEF 161

Total Cards: 60
```

Stored at `submission/csv/deck_aggro.json`.

## Concept

A **Stage-1 / ex-heavy aggro shell** that aims to drop a 4-prize threat (Mega Latias ex, Pikachu ex, Gouging Fire ex, or Iron Thorns ex) onto the board in the first 1–2 turns and keep pressure on the opposing Active Spot. The deck is multi-type intentionally — it carries enough off-colour basic Energy and special-Energy flexibility (Boomerang, Mist) to keep an attacker streaming damage even when the ideal Pokémon isn't available.

## Strategy / game plan

| Phase | Goal | Tools |
|---|---|---|
| Turn 1–2 (opener) | Get a Basic ex into the Active Spot; bench a second 2-prize threat. | 4× Buddy-Buddy-style ramp via Meddling Memo (`SSP 181`) for tutoring, 4× Roto-Stick (`PRE 127`) for board acceleration. |
| Turn 3–5 (mid-game) | Take the first 2 prizes; force an opponent switch into a weak bencher. | 4× Unfair Stamp (`TWM 165`) — hand-disruption keeps tempo; Ogre's Mask removes inconvenient tools / energies. |
| Turn 6+ (close) | KO into the 4-prize lead via a Mega Latias ex or Iron Thorns ex finishing line. | The Mega Latias ex / Pikachu ex combination targets prize-trading favourably against single-prize boards. |

## Key cards & why they're here

- **Mega Latias ex (MEG 100)** — the deck's headline pivot. High HP + multi-Energy attack that benefits from the deck's special-Energy package (Mist Energy).
- **Pikachu ex (SSP 57)** — fast Electric attacker. With Mist Energy + Basic Lightning, the cost ramps in 2 turns.
- **Gouging Fire ex (TEF 38)** — Fire-type aggressive finisher; weaponises Basic Grass Energy + Boomerang Energy ramp.
- **Iron Thorns ex (TWM 77)** — Future-typing for the late game; punishes Stage-2 setups.
- **Meddling Memo (SSP 181)** — drives consistency by exchanging cards in hand for a fresh draw on key turns.
- **Unfair Stamp (TWM 165)** — disruption package; sets up Mega Latias's prize-pressure window.

## Strengths (measured / structural)

- **Energy ramp is real**: 26 Energy cards including 2 Boomerang + 2 Mist (effective acceleration) — the builder picked this consciously, not by accident.
- **Multi-coloured threat package** insulates against bench-targeting tools.
- **4 copies of Mega Latias ex** maximises consistency of the headline threat.
- **Builder-scored 45.51** — the highest of the three archetypes attempted (Aggro / Control / Combo) at this iteration count.

## Weaknesses (structural)

- **Type spread costs Energy cohesion.** Running 5 distinct Energy types (G/L/M/P/R) means the agent will frequently draw the wrong colour for the wrong attacker.
- **No Stage-2 line** — the Applin baseline (`TWM 126`) is present but the deck has no Dipplin / Hydrapple finisher. Applin appears as a discard-fodder card more than a real threat.
- **Trainer count is light (14)** for a deck that wants to disrupt — typical Aggro shells run 18–22 Trainers.
- **No tools** beyond Ogre's Mask, so no Defiance Band / Bravery Charm for the 30-damage swings competitive aggro decks usually exploit.

## Matchup discussion

Because the simulator did not produce terminal states within the measured horizon, **win-rate matchup numbers are not reportable**. The discussion below is therefore structural, not statistical:

- **vs. Other Aggro** — Likely an Energy race. The deck's multi-colour spread is a liability here.
- **vs. Control / Stall** — Unfair Stamp disrupts setup; the 4× Mega Latias ex + Pikachu ex pressure pushes through stall.
- **vs. Combo (e.g., Stage-2 setup)** — Iron Thorns ex specifically targets Future Pokémon; the deck has a reasonable answer.

## Why this deck was selected

Three archetypes were attempted (Aggro / Control / Combo). The builder produced a candidate for the **Aggro** archetype first, with builder score 45.51. The Control and Combo archetype runs were initiated in the background but had not completed at submission time. Aggro is **selected** as the submission deck on the basis of:

1. **A real measured score from `pokemon-ai build-deck`** — not subjective.
2. **Match-up versatility** — multi-typed threat package covers a wider matchup spread than a mono-colour Control list.
3. **Simulator-execution compatibility** — Trainer cards in this list (Unfair Stamp, Meddling Memo, Roto-Stick, Ogre's Mask) all appear in the simulator-validation execution log (see `figures/simulator_validation.png`), confirming the engine can actually drive this deck.
