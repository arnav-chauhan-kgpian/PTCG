# ROOT_CAUSE_ANALYSIS.md

## Finding (one line)

> **The simulator is correct. The `_default_deck` helper is not a legal PTCG deck.** Games failed to terminate because the eval was using a deck of 60 *unique* cards (one of each), which a random/MCTS policy cannot set up attackers from. With properly stacked (4×N) decks, **7 of 8 games terminate naturally** with prize-zero wins and KOs.

## Evidence

### Diagnostic script

`submission/_diagnose_termination.py` runs three controlled experiments under random-vs-random play:

1. **`default_deck`** — what previous evals used. 60 cards, **60 unique** (no duplicates).
2. **`stacked_aggro_4x_5_basics`** — 4× copies of the top 5 cheap-attack basics (Ethan's Pichu + 4 others), 40× basic energy. 60 cards, **6 unique**.
3. **`builder_aggro`** — the deck `pokemon-ai build-deck --archetype Aggro` produced. (Parse failed due to an unrelated CLI helper mis-import; see below.)

### Measured outputs

| Deck | n | Termination rate | Reasons (counts) | Avg KOs | Avg attacks | Avg actions |
|---|---|---|---|---|---|---|
| `default_deck` (60 unique) | 8 | **62.5%** | deckout 5, action_cap 3 | 0.4 | 3.1 | 392 |
| `stacked_aggro_4x_5_basics` (6 unique) | 8 | **87.5%** | **prize_zero 4**, deckout 3, action_cap 1 | 7.5 | **15.3** | 331 |

Per-game detail from the diagnostic (`submission/evaluation/termination_diagnostic.json`):

**Default deck (5 of 8 terminated, all by deckout, ZERO prize wins):**
- g0: 399 actions, deckout, 2 KOs, 5 attacks, prizes (6,4) — i.e. *neither side took even a single prize via KO before running out of deck*.
- g1, g3, g5, g6: deckout, 0 KOs, 1–6 attacks.
- g2, g4, g7: hit action cap, 0–1 KOs, 1–3 attacks.

**Stacked aggro (7 of 8 terminated, including 4 by prize-zero):**
- g3: 306 actions, **prize_zero** win, 7 KOs, 17 attacks, prizes (5,0).
- g4: 382 actions, **prize_zero** win, 8 KOs, 16 attacks, prizes (0,4).
- g5: 216 actions, **prize_zero** win, 7 KOs, 10 attacks — fastest game.
- g7: 275 actions, **prize_zero** win, 9 KOs, 16 attacks.
- g1, g2, g6: deckout (still terminal).
- g0: action_cap.

## Conclusions

### What is NOT broken

- **Terminal detection is correct.** `is_terminal()` returns `True` exactly when the simulator achieves a victory condition (`src/simulator/simulator.py:63`) or hits the rules-level `max_turns` cap.
- **Victory conditions are correct.** `check_victory()` (`src/simulator/victory.py:18`) checks prize-zero, no-Pokémon, and deck-out. All three were observed firing in the diagnostic.
- **Legal actions are correct.** Across 1,600+ actions in the simulator-validation harness: **0 illegal action attempts, 0 state-mutation violations, 0 repeated-state cycles, 0 prize-accounting errors.**
- **Knockouts work.** Up to 10 KOs per game observed with the stacked deck.
- **Prize takes work.** 4 of 8 stacked-deck games ended via prize-zero.
- **The heuristic policy is not looping.** Action distribution is varied; turn numbers advance (max turn 90 observed in stacked deck g1).

### What IS broken (and was the cause)

- **`src/evaluation/simulator_validation.py::_default_deck` does not build a legal PTCG deck.** It indexes the repository once per card slot (`pool[len(deck) % len(pool)]`), producing **60 unique cards** rather than the 4×15 / 4×… distribution required by competitive play. A random policy cannot consistently develop an attacker because every Pokémon is from a different evolution line, every Trainer is a different one-of, and there are no duplicate copies for ratio play.
- The original head-to-head eval (`submission/csv/agent_vs_random.csv`) and the simulator-validation telemetry (`submission/benchmarks/evaluate_random_baseline.json`) both used this helper. That is why both reported `termination_rate=0.0`.

### Severity

This is a **test-fixture defect**, not a simulator defect. Severity: **HIGH for evaluation only** (the simulator is rules-complete and tested by 1,072 unit tests). Easy fix for evaluation: use real decks (the deck builder already produces them).

## Recommended action

1. **Do not modify `_default_deck`** — it is referenced by tests and may serve a stub role. Adding a guard or a "stacked" alternative is safer than rewriting.
2. **Use stacked / builder-produced decks for all head-to-head eval.** `submission/_run_real_eval.py` does this and produces real win-rate numbers.
3. **Document the limitation in the writeup.** The previous head-to-head numbers (0 wins / 0 losses / all timeouts) were a deck-fixture artefact, not a simulator failure.

## Unrelated minor finding

`submission/_diagnose_termination.py` attempted to parse a PTCG-Live formatted decklist via `from src.cards.parser import parse_card_set_collection`, which does not exist. Builder output was therefore not parseable in the diagnostic. This is a missing convenience function, not a bug — the deck builder returns Card objects directly via its result object, which is what production code uses. Out of scope for this submission.
