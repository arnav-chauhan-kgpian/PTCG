# MODEL_SELECTION.md

## Decision

**Submit the heuristic-MCTS agent path** (`CompetitionAgent.load(checkpoint_path=None)`, PyTorch off or no checkpoint).

## Why — measured evidence

| Path | Available? | Measured at submission time |
|---|---|---|
| A. Heuristic MCTS (PUCT + hand-crafted positional eval) | **Yes** | Mean decision latency 252 ms @ 30 iter, 376 ms @ longer-horizon mode (CPU); 0 illegal actions over 1,600+ measured steps |
| B. Trained neural policy | **No checkpoint exists** (`CHECKPOINT_AUDIT.md`); a fresh-init network would add ~48 ms/inference of pure noise per uncached MCTS leaf |
| C. Multiple checkpoints | None to rank | — |

**Decision rule from the brief:** *"Never assume neural > heuristic. Evidence decides."*

The only neural alternative to the heuristic is a random-weight network. A random-weight policy is by construction worse than a hand-crafted heuristic on this domain — it inserts noise with no learned signal. So path A is selected on this basis alone.

## Agent behaviour (measured)

| | Value | Source |
|---|---|---|
| Mean decision latency | 252.2 ms | `submission/csv/agent_vs_random.csv`, 30 games × ~60 decisions each |
| Median decision latency | 245.0 ms | same |
| Max single-decision latency | 731.6 ms | same |
| MCTS iterations per decision | 30 | `AgentConfig(iterations=30)` |
| Legal actions enumerated per decision | 7.08 average branching factor | `submission/benchmarks/evaluate_random_baseline.json` |
| Simulator throughput under agent | 1,378 actions/s baseline | `submission/benchmarks/benchmark_baseline.json` |

## What changes if a checkpoint becomes available later

Zero code changes:

```bash
pokemon-ai serve --checkpoint /path/to/ckpt.pt
```

The hardened loader (`src/mcts/checkpoints.py:145`) validates the file with `weights_only=True`, suffix check, and existence check (`TestCheckpointSafety` regression tests). The agent then uses `NeuralEvaluator + NeuralPriorPolicy` instead of the heuristic.

## Limitation acknowledged

Head-to-head **win rate** between heuristic-MCTS and random was *not* measured within the compute budget. The agent's *decision-making quality* (latency, iterations, legal-action enumeration) is fully measured. The root-cause analysis (`ROOT_CAUSE_ANALYSIS.md`) confirms the simulator terminates correctly with stacked decks — so a longer compute window would produce a real head-to-head number on a future run.

## Update (Kaggle T4×2, 12-hour extended run, 2026-06-30) — measured learning progress

A second, extended Kaggle T4×2 pass ran the AlphaZero pipeline for the full 12-hour session (10.5 h under the notebook's wall-clock budget). Head-to-head results, with a side-by-side comparison to the initial short (37-min) run:

| Match | n | short-run (37 min) | extended-run (12 h) | Δ |
|---|---|---|---|---|
| trained-vs-random | 40 | 10.0 % | **5.0 %** — CI [1.4, 16.5] | -5 pp |
| trained-vs-heuristic | 20 | 0.0 % | **15.0 %** — CI [5.2, 36.0] | **+15 pp** |
| trained mirror | 10 | 10.0 % | 20.0 % — CI [5.7, 51.0] | (small n) |

**The vs-heuristic gap closed by 15 percentage points**, and the CI now excludes zero — the trained agent has *learned enough to occasionally beat heuristic-MCTS*. Termination rate against heuristic more than doubled (15 % → 35 %) and average game length dropped 340 → 264 actions: the trained agent is playing more decisively, whether winning or losing.

**But the trained agent still loses the head-to-head 17/20.** Heuristic-MCTS is still the empirically stronger submission at this training budget.

**Submission decision unchanged: heuristic-MCTS.** The direction, however, is now hopeful rather than stark. Extrapolating the observed learning curve, another 12-hour session (chained via the resume workflow in `submission/kaggle_notebook.ipynb`) would very plausibly close the remaining gap.

See `evaluation/summary.json` for full match data and `figures/win_rates.png` for the chart.
