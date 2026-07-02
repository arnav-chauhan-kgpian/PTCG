"""Multi-run learning-curve figure across all training runs to date."""
from __future__ import annotations

import json
import pathlib

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = pathlib.Path(__file__).parent
FIG = ROOT / "figures"
MEDIA = ROOT / "media"

summary = json.loads((ROOT / "evaluation" / "summary.json").read_text(encoding="utf-8"))
runs = summary["multi_run_summary"]["runs"]
agg = summary["multi_run_summary"]["aggregate_vs_heuristic"]

plt.rcParams.update({
    "figure.dpi": 130, "savefig.dpi": 160,
    "font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
})

fig, ax = plt.subplots(figsize=(10, 5))
xs = list(range(1, len(runs) + 1))
vs_rand = [r["vs_random_pct"] for r in runs]
vs_heur = [r["vs_heuristic_pct"] for r in runs]
mirror  = [r["mirror_pct"] for r in runs]

ax.plot(xs, vs_rand, "o-", color="#00C49F", linewidth=2, markersize=9, label="vs Random")
ax.plot(xs, vs_heur, "s-", color="#FF647C", linewidth=2, markersize=9, label="vs Heuristic-MCTS")
ax.plot(xs, mirror, "^-", color="#FFB623", linewidth=2, markersize=9, label="Mirror (p0)")

ax.axhline(50, color="#666", linestyle="--", linewidth=1, alpha=0.7,
            label="fair coin (50%)")
ax.axhline(agg["mean_win_rate_pct"], color="#FF647C", linestyle=":", linewidth=1.5,
            alpha=0.6, label=f"aggregate vs heuristic ({agg['mean_win_rate_pct']}%)")

ax.set_ylim(-3, 55)
ax.set_xlim(0.5, len(runs) + 0.5)
ax.set_xticks(xs)
ax.set_xticklabels([f"Run {i}\n{r['training'].split(' / ')[0]}" for i, r in zip(xs, runs)],
                    fontsize=8.5)
ax.set_ylabel("trained-agent p0 win rate (%)")
ax.set_title("Trained-agent win rate across four independent training runs\n"
              "(all evaluated on the stacked aggro deck, MCTS 32 iter, T4×2)")
ax.legend(loc="upper right", fontsize=9)
ax.grid(True, alpha=0.25, axis="y")

# Annotate each Run's vs-heuristic point
for i, r in zip(xs, runs):
    ax.text(i, r["vs_heuristic_pct"] + 2, f"{r['vs_heuristic_pct']}%",
            ha="center", fontsize=8.5, color="#FF647C", fontweight="bold")

plt.tight_layout()
fig.savefig(FIG/"multi_run_learning.png", bbox_inches="tight")
fig.savefig(MEDIA/"multi_run_learning.png", bbox_inches="tight")
plt.close()
print("saved multi_run_learning.png")
