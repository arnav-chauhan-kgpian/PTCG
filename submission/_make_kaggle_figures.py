"""Generate the three Kaggle-run figures locally from the measured summary."""
from __future__ import annotations

import json
import pathlib

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = pathlib.Path(__file__).parent
FIG = ROOT / "figures"
FIG.mkdir(exist_ok=True)
MEDIA = ROOT / "media"
MEDIA.mkdir(exist_ok=True)

plt.rcParams.update({
    "figure.dpi": 130, "savefig.dpi": 160,
    "font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
})

summary = json.loads((ROOT / "evaluation" / "summary.json").read_text(encoding="utf-8"))
matches = summary["matches"]
labels = [m["label"] for m in matches]
rates  = [m["p0_win_rate"] for m in matches]
lows   = [r - m["p0_win_rate_wilson_95_ci"][0] for r, m in zip(rates, matches)]
highs  = [m["p0_win_rate_wilson_95_ci"][1] - r for r, m in zip(rates, matches)]

# Figure 1 — win-rate bar with 95% CIs
fig, ax = plt.subplots(figsize=(9, 4))
colors = ["#5E5CFF", "#FF647C", "#FFB623"]
bars = ax.barh(labels, rates, xerr=[lows, highs],
                color=colors, capsize=5, edgecolor="white", linewidth=1.5)
ax.axvline(0.5, color="#666", linestyle="--", linewidth=1, alpha=0.7,
            label="fair-coin (50%)")
ax.set_xlim(0, 1.0); ax.set_xlabel("p0 win rate (Wilson 95% CI)")
ax.set_title("Trained agent — head-to-head matchups (Kaggle T4×2)")
for i, (r, m) in enumerate(zip(rates, matches)):
    ax.text(r + max(highs[i], 0.02) + 0.02, i,
            f"{r:.1%}  n={m['n_games']}", va="center", fontsize=9)
ax.legend(loc="lower right")
plt.tight_layout()
fig.savefig(FIG/"win_rates.png", bbox_inches="tight")
fig.savefig(MEDIA/"win_rates.png", bbox_inches="tight")
plt.close()
print("✓ win_rates.png")

# Figure 2 — termination rate + avg actions per match
term = [m["termination_rate"] for m in matches]
avga = [m["avg_actions_per_game"] for m in matches]
fig, ax = plt.subplots(figsize=(9, 4))
x = list(range(len(labels))); w = 0.4
b1 = ax.bar([i - w/2 for i in x], term, w, color="#5E5CFF",
              label="termination rate")
ax2 = ax.twinx()
b2 = ax2.bar([i + w/2 for i in x], avga, w, color="#FF647C",
               label="avg actions / game")
ax.set_xticks(x); ax.set_xticklabels(labels, rotation=10)
ax.set_ylim(0, 1.0); ax.set_ylabel("termination rate")
ax2.set_ylabel("average actions per game")
ax.set_title("Game completion: terminations and action counts (max 400)")
for r, v in zip(b1, term):
    ax.text(r.get_x() + r.get_width()/2, v + 0.02, f"{v:.0%}", ha="center", fontsize=9)
for r, v in zip(b2, avga):
    ax2.text(r.get_x() + r.get_width()/2, v + 8, f"{v:.0f}", ha="center", fontsize=9)
lines, labs = ax.get_legend_handles_labels()
lines2, labs2 = ax2.get_legend_handles_labels()
ax.legend(lines + lines2, labs + labs2, loc="upper left", fontsize=9)
plt.tight_layout()
fig.savefig(FIG/"termination_kos.png", bbox_inches="tight")
fig.savefig(MEDIA/"termination_kos.png", bbox_inches="tight")
plt.close()
print("✓ termination_kos.png")

# Figure 3 — training summary table
fig, ax = plt.subplots(figsize=(8, 3.5))
ax.axis("off")
t = summary["training"]
rows = [
    ["rounds requested", t["rounds_requested"]],
    ["rounds completed", t["rounds_completed"]],
    ["promotions", t["promotions"]],
    ["elapsed (s)", t["elapsed_s"]],
    ["best checkpoint", str(t["best_checkpoint"])],
]
if "checkpoint_saved" in t:
    rows.append(["checkpoint saved", t["checkpoint_saved"]])
tab = ax.table(cellText=rows, colLabels=["metric", "value"],
                cellLoc="left", loc="center", colWidths=[0.32, 0.62])
tab.auto_set_font_size(False); tab.set_fontsize(10); tab.scale(1, 1.5)
ax.set_title("Training run summary (Kaggle T4×2)", pad=12)
if t.get("note"):
    fig.text(0.5, 0.04, t["note"], ha="center", fontsize=8,
              style="italic", color="#444", wrap=True)
plt.tight_layout()
fig.savefig(FIG/"training_summary.png", bbox_inches="tight")
fig.savefig(MEDIA/"training_summary.png", bbox_inches="tight")
plt.close()
print("✓ training_summary.png")
print("Done.")
