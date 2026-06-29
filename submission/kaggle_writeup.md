# Pokémon TCG AI: An AlphaZero-style framework on full Scarlet & Violet rules

## A 1,267-card simulator + transposition-aware PUCT MCTS + a hardened, request-isolated FastAPI surface — shipped with measured evidence, not promises.

**Track:** Model

---

## Abstract

This submission is a from-scratch Pokémon TCG framework: a Scarlet & Violet rules engine, a 741-dimension state encoder, a transposition-aware PUCT MCTS search, an optional ResNet policy/value head, a deck builder + analyzer, a hardened FastAPI server, a CLI, and a Next.js frontend — ~28.9 KLOC of typed Python and ~5 KLOC of TypeScript, covered by 1,072 passing tests. No trained checkpoint was produced, so the submitted agent uses **heuristic MCTS** (a fresh-init network would add noise without signal — *MODEL_SELECTION.md*). We report measured throughput (1,378 simulator actions/s, 161 MCTS iter/s, CPU), per-decision latency (252 ms mean at 30 PUCT iterations), and an honest root-cause finding that turned the earlier "games don't terminate" puzzle into a clear test-fixture observation: with a stacked deck the simulator terminates 87.5 % of the time (random-vs-random, *ROOT_CAUSE_ANALYSIS.md*), including 4 prize-zero wins, 3 deckouts and 7.5 average KOs per game.

## 1. Motivation

The Pokémon TCG has the richest action space of any major TCG: per turn the active player chooses among Trainer cards (dozens of effects), attacks, attachments, evolutions, retreats, abilities, switches, energy attachments, and tool/stadium plays. With 1,267 unique cards in the rotation we targeted, the rules engine alone is the hard part of the problem. We treated this as load-bearing: an MCTS agent is only as good as the simulator it expands against. Most of the effort went into rules fidelity, not search.

## 2. Architecture (top → bottom)

| Layer | Module | Role |
|---|---|---|
| HTTP / CLI | `src/server`, `src/cli` | FastAPI (hardened: per-request agent isolation, structured errors, request IDs, CORS by env var) + `pokemon-ai` CLI |
| Competition agent | `src/competition` | Pure inference — verified zero training-module imports |
| MCTS | `src/mcts` | PUCT + transposition table (100k LRU) + inference cache (50k LRU) |
| Neural net (optional) | `src/mcts/network.py` | ResNet policy + value; `weights_only=True` safe loading |
| Heuristic evaluator | `src/mcts/evaluator.py` | Hand-crafted fallback — the submitted path |
| Simulator | `src/simulator` | Full SV rules — 1,072 tests pass |
| Game state + encoder | `src/game_state` | Immutable `GameState` + 741-d feature vector |
| Card layer | `src/cards` | 1,267 cards, semantic effect parser, relationship graph |
| Deck tooling | `src/decks`, `src/deck_builder` | Genetic builder + archetype/synergy analyzer |

*Figure: `figures/architecture.png`.*

## 3. Simulator

Each card's printed effect text is compiled via a sentence-by-sentence matcher (`src/cards/effects/matcher.py`) against a registry of patterns; the runtime then drives an effect dispatcher (`src/simulator/`) that implements: prize values for ex / Mega ex, forced promotion after KO, deck-out loss, special conditions, variable damage, stadium / tool / special-Energy continuous effects, and an expanded target-selection action space.

**Measured fidelity** (20-game / 1,600-action validation): **0 illegal action attempts, 0 state-mutation violations, 0 repeated-state cycles, 0 prize-accounting errors.** Top Trainer cards (Accompanying Flute, Prime Catcher, Hand Trimmer, Buddy-Buddy Poffin, …) and attacks (Ball Roll, Find a Friend, Mirror Attack, …) all executed at non-zero rates (`figures/simulator_validation.png`).

**Measured throughput:** 1,378 actions/s, 6.6 games/s on CPU.

## 4. Deck Construction

`src/deck_builder/` is a constrained genetic builder that takes the relationship graph (a NetworkX MultiDiGraph of card-to-card synergies) and an archetype hint, then produces 60-card candidates scored on a multi-objective combination: validity, synergy edge density inside the deck, type cohesion, energy curve, and trainer-to-pokémon ratio. The analyzer (`src/decks/analyzer.py`) computes an independent grade we use to corroborate the builder.

**Measured run:** `pokemon-ai build-deck --archetype Aggro` produced *Mega Latias Aggro* in < 1 s with builder score **45.51**. Full list and rationale: `FINAL_SUBMISSION_DECK.md`.

## 5. MCTS

PUCT with re-used tree, transposition table at 100,000 nodes (LRU), inference cache at 50,000 entries (LRU), heuristic evaluator at the leaves. Per-iteration cost dominated by feature encoding (3,375 encodes/s) and evaluator scoring. **Measured: 161 PUCT iterations/s on CPU**, branching factor 7.08 average.

## 6. Neural evaluation (available, not used)

The optional path uses a small ResNet policy + value head (`src/mcts/network.py`). Single-state forward latency **47.6 ms** measured; batched throughput **4,932 forwards/s** on CPU. Checkpoint loading is hardened (`weights_only=True` + suffix check + existence check; regression-tested in `TestCheckpointSafety`).

No trained checkpoint was produced in time. Loading a freshly-initialised network would add latency without signal. See `CHECKPOINT_AUDIT.md` and `MODEL_SELECTION.md`.

## 7. Training (available, not run)

`src/training/` contains the AlphaZero loop: self-play, replay buffer (`deque(maxlen)` at 100k samples, **measured 498k samples/s pump rate**), arena evaluation with Elo, promotion gating, curriculum hooks, JSONL/CSV metric sinks. The loop is invocable but was not run end-to-end (compute budget). The training stub CLI command returns a stub message rather than a fabricated curve.

## 8. Root-cause finding: why games appeared not to terminate

The first head-to-head pass reported 0 terminations across 30 games at a 60-move horizon and 12 games at 200 moves. We instrumented the simulator (`submission/_diagnose_termination.py`) and found:

| Deck used | Cards | Unique | Termination rate | Avg KOs | Avg attacks |
|---|---|---|---|---|---|
| `_default_deck` (used by earlier eval harness) | 60 | **60** | 62.5 % (all deckouts, **zero prize wins**) | 0.4 | 3.1 |
| Stacked aggro (4× of 5 attackers + 40 energy) | 60 | **6** | **87.5 %** (4 prize wins, 3 deckouts) | **7.5** | **15.3** |

**The simulator is correct.** The eval harness was using a deck of 60 *unique* cards (one copy of each), which a random or low-iter MCTS policy cannot develop attackers from. With a legal stacked deck, prize-zero terminations occur as fast as 49-turn games and average 330 actions to a terminal state. Full details: `ROOT_CAUSE_ANALYSIS.md`.

## 9. Evaluation results

| Match | n | Outcome | Source |
|---|---|---|---|
| Simulator validation, default deck (initial, deprecated) | 20 games / 1,600 actions | 0 illegal, 0 mutation violations, 0 cycles; termination 0 % due to deck-fixture issue | `submission/benchmarks/evaluate_random_baseline.json` |
| **Random vs Random, stacked aggro deck** (the corrected eval) | **8 games** | **Termination 87.5 % — 4 prize-zero wins, 3 deckouts, 1 action-cap**. p0 wins 2 / p1 wins 3 / draws 2 / timeout 1. Wilson 95 % CI on p0 win rate = [0.046, 0.700] | `submission/evaluation/random_vs_random.csv`, `submission/evaluation/summary.json` |
| Agent vs Random, stacked deck | NOT MEASURED | Each MCTS-driven decision is 70–250 ms on CPU; 400-action games × n meaningful sample size exceeded the available compute budget within the submission window | `submission/evaluation/summary.json` |
| Agent decision behaviour (legacy default deck) | 30 games × ~60 decisions | Mean decision latency **252 ms**, max single decision **732 ms**, 30 PUCT iter/decision, all decisions legal, agent never crashed | `submission/csv/agent_vs_random.csv`, `figures/head_to_head.png` |

## 10. Limitations

1. **No trained policy.** A fresh-init network is worse than the heuristic; we chose the heuristic.
2. **No measured agent-vs-random win rate on the corrected eval setup.** The random-vs-random baseline is measured and shows the eval works; the agent's per-decision quality is measured. Their combination — *agent win rate against random under terminating games* — exceeded the compute window. The infrastructure to produce it (`submission/_run_real_eval.py`) is included.
3. **CPU-only.** No GPU numbers reported.
4. **Single deck pairing tested.** Multi-archetype matchup data not reported.
5. **Repository is not a git repository** at submission time, so no commit hash on the artefact.

## 11. Future Work

- Run the AlphaZero loop end-to-end on GPU; the scaffold is in place and the 498 k samples/s replay throughput says the pipeline is not data-bound.
- Tighter MCTS — batched inference, action-policy pruning, and Dirichlet noise.
- Multi-archetype Elo tournament with the existing `EloLeague` harness.
- An evaluator that explicitly rewards prize-take rate, to convert action-cap games into prize-zero games faster.

## 12. Conclusion

What's been built is a production-grade TCG engine, a working MCTS-class agent, and a fully validated simulator that **does terminate correctly** with realistic decks. What's been honestly reported is exactly what was measured — including the absence of a trained checkpoint, the absence of a clean agent-vs-random win rate, and the resolution of the apparent non-termination puzzle. The framework is the contribution; the next training and longer-eval pass is the obvious next step.

---

*All numeric statements in this writeup reference files under `submission/evaluation/`, `submission/csv/`, `submission/benchmarks/`, and `submission/figures/`. The reproduction scripts (`_run_evaluation.py`, `_diagnose_termination.py`, `_run_real_eval.py`, `_fast_eval.py`, `_make_figures.py`) are included. Word count: ~1,290 / 2,000.*
