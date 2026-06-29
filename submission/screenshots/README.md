# Screenshots

Browser-driven screenshot capture was not available in this environment (no Chrome/headless tool was connected). Instructions for manual capture follow.

## How to capture

```powershell
# Terminal 1 — backend
cd D:\PTCG
.\venv\Scripts\Activate.ps1
pokemon-ai serve --host 0.0.0.0 --port 8000

# Terminal 2 — frontend
cd D:\PTCG\frontend
npm run dev
```

Open `http://localhost:3000` in a 1440×900 Incognito Chrome window (dark mode default). Capture the following pages with the built-in screen-capture tool (Windows: Win+Shift+S). Save into this directory using the suggested filenames:

| Filename | URL | What to frame |
|---|---|---|
| `01_landing.png` | `/` | Hero + animated headline + feature grid in one shot |
| `02_battle_arena.png` | `/battle` | Whole board + decision panel showing MCTS visit shares |
| `03_battle_alt_move.png` | `/battle` | After clicking an alternative move — the PV updates |
| `04_dashboard.png` | `/dashboard` | Charts + system health (single screen) |
| `05_deck_builder.png` | `/deck-builder` | Card search + 60/60 counter + energy curve |
| `06_deck_analyzer.png` | `/deck-analyzer` | Sample deck pre-filled, after clicking *Analyze* |
| `07_cards.png` | `/cards` | Filterable explorer + open card detail modal |
| `08_analysis.png` | `/analysis` | Top moves table + PV + neural value gauge |
| `09_training.png` | `/training` | Loss curves + arena Elo + promotion history |
| `10_benchmarks.png` | `/benchmarks` | Performance breakdown + history |
| `11_settings.png` | `/settings` | Theme toggle + integrations |
| `12_swagger.png` | `http://localhost:8000/docs` | FastAPI auto-generated API reference |

## License check before attaching

Verify with `LICENSE_AUDIT.md` that the captured screen contains **no rendered Pokémon card art** (the frontend does not ship card art, so default state is safe — but check the browser tab title and any "Card" detail modals).

## Substitution

If screenshots cannot be produced, the writeup remains usable: every page is described in *Architecture* and *Results*, and the architecture and benchmark figures in `figures/` substitute for visual proof of the engine's working state.
