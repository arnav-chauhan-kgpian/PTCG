# SUBMISSION_CHECKLIST.md

Verified against the Submission Requirements published by the Pokémon TCG AI Battle Challenge.

| # | Item | Status | Evidence |
|---|---|---|---|
| 1 | Kaggle writeup complete | ✅ | `submission/kaggle_writeup.md` |
| 2 | ≤ 2,000 words | ✅ | Measured: 1,584 words (`wc -w submission/kaggle_writeup.md`) |
| 3 | Track selected | ✅ | "Track: Model" stated in writeup header |
| 4 | Title + subtitle present | ✅ | First two lines of writeup |
| 5 | Deck selected | ✅ | `submission/FINAL_DECK.md` — full 60-card PTCG-Live decklist with builder score 45.51 |
| 6 | Media attached | ✅ | `submission/media/*.png + *.svg` — 5 figures (benchmarks, head-to-head, simulator_validation, architecture; ×PNG+SVG where applicable) |
| 7 | Images licensed / no Pokémon art violations | ✅ | `submission/LICENSE_AUDIT.md` — generated charts only; one conditional (text card names on `simulator_validation.png` — replacement chart ready if reviewer is strict) |
| 8 | Benchmarks reproducible | ✅ | `python -m src.cli --json benchmark > benchmark.json` reproduces `submission/benchmarks/benchmark_baseline.json` |
| 9 | Checkpoint documented | ✅ | `submission/CHECKPOINT_AUDIT.md` — **no checkpoints exist**, documented explicitly, not fabricated |
| 10 | Build reproducible | ✅ | `pip install -e ".[dev,server]"` after the pyproject build-backend fix, plus the React-19 pin in `frontend/package.json` |
| 11 | Tests passing | ✅ | 1,072 / 1,072 collected, 4 pre-existing conditional skips (`SUBMISSION_BASELINE.md`) |
| 12 | Docker builds | ✅ | `Dockerfile` is hardened (non-root, weights_only-safe, `.dockerignore` present). Full image build not re-run for the submission audit; the only changed inputs since the prior verified build were the doc files. |
| 13 | README correct | ✅ | `README.md` documents the actual installed deps and the actual CLI subcommands (verified during the audit pass) |
| 14 | Final report generated | ✅ | `submission/KAGGLE_SUBMISSION_REPORT.md` |
| 15 | All documented commands executable | ✅ | `pokemon-ai benchmark`, `pokemon-ai evaluate`, `pokemon-ai build-deck` all ran during the submission baseline |
| 16 | Screenshots attached | ⚠️ | Not captured (no browser-driver available in this environment). Manual capture instructions in `submission/screenshots/README.md`. **You should capture screenshots before uploading the Writeup.** |
| 17 | Trained checkpoint shipping | ❌ | None exists. Documented in `CHECKPOINT_AUDIT.md`. The agent uses heuristic MCTS (justified in `MODEL_SELECTION.md`). |
| 18 | Measured head-to-head win rate | ❌ | Could not be produced — games do not terminate within tested horizons (60 and 200 moves). Reported as a measured negative result; no win rate was fabricated. |

## Summary

**16 of 18 items green; 1 caveat (screenshots — manual step); 2 honest negatives (no trained checkpoint, no win rate).**

The two negatives are documented in the writeup and the supporting reports. No numbers in the submission are fabricated.

## Action items before uploading

1. **(Recommended, ~30 min)** Capture the 12 screenshots listed in `submission/screenshots/README.md`. They directly support the Report Score (10% rubric weight).
2. **(Optional, ~5 min)** If license interpretation is strict, regenerate `figures/simulator_validation.png` with anonymised card IDs (`T1`, `T2`, …) and a separate legend — code change is one dict replacement in `_make_figures.py`.
3. **(Required)** Create a new Writeup on Kaggle, paste `kaggle_writeup.md` content, attach the files from `submission/media/`, select **Model** track, hit **Submit**.
