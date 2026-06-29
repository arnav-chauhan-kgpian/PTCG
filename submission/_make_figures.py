"""Generate publication-quality figures from measured data only."""
from __future__ import annotations

import json
import pathlib

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = pathlib.Path(__file__).parent
FIG = ROOT / "figures"
FIG.mkdir(exist_ok=True)

plt.rcParams.update({
    "figure.dpi": 120,
    "savefig.dpi": 160,
    "font.size": 10,
    "axes.titlesize": 12,
    "axes.spines.top": False,
    "axes.spines.right": False,
})


def fig_benchmarks():
    data = json.loads((ROOT / "benchmarks" / "benchmark_baseline.json").read_text())
    bars = [
        ("Replay buffer\n(samples/s)", data["replay_samples_per_sec"]),
        ("Network batch\n(forwards/s)", data["network_batch_per_sec"]),
        ("Encoder\n(encodes/s)", data["encoder_per_sec"]),
        ("Simulator actions\n(actions/s)", data["simulator_actions_per_sec"]),
        ("MCTS\n(iter/s)", data["mcts_iterations_per_sec"]),
        ("Simulator games\n(games/s)", data["simulator_games_per_sec"]),
    ]
    labels = [b[0] for b in bars]
    values = [b[1] for b in bars]
    fig, ax = plt.subplots(figsize=(9, 4.5))
    colors = ["#5E5CFF", "#7E3CFF", "#26C9FF", "#00C49F", "#FFB623", "#FF647C"]
    bars_obj = ax.barh(labels, values, color=colors)
    ax.set_xscale("log")
    ax.set_xlabel("operations per second (log scale)")
    ax.set_title("Measured throughput — Pokémon TCG AI, CPU baseline")
    for rect, v in zip(bars_obj, values):
        ax.text(v * 1.05, rect.get_y() + rect.get_height() / 2,
                f"{v:,.1f}", va="center", fontsize=9)
    plt.tight_layout()
    fig.savefig(FIG / "benchmarks.png", bbox_inches="tight")
    fig.savefig(FIG / "benchmarks.svg", bbox_inches="tight")
    plt.close(fig)
    print(f"  saved benchmarks.png/svg")


def fig_head_to_head():
    summary_path = ROOT / "csv" / "agent_vs_random_summary.json"
    if not summary_path.exists():
        print("  agent_vs_random_summary.json not present yet — skipping")
        return
    d = json.loads(summary_path.read_text())
    fig, axes = plt.subplots(1, 2, figsize=(9, 4))

    # Outcome breakdown
    ax = axes[0]
    n = d["n_games"]
    counts = [d["wins"], d["draws"], d["losses"]]
    labels = [f'wins ({d["wins"]})', f'draws ({d["draws"]})', f'losses ({d["losses"]})']
    colors = ["#00C49F", "#FFB623", "#FF647C"]
    ax.pie(counts, labels=labels, colors=colors, autopct="%1.0f%%",
           startangle=90, wedgeprops={"edgecolor": "white", "linewidth": 2})
    ax.set_title(f"Agent vs Random — {n} games\nMCTS@{d['agent_iterations_per_decision']} iter, max {d['max_moves']} moves")

    # Decision latency vs search iters
    ax = axes[1]
    latency = d.get("avg_decision_latency_ms", 0)
    iters = d.get("avg_search_iters", 0)
    moves = d.get("avg_moves_per_game", 0)
    metrics = [latency, iters, moves]
    metric_names = ["Decision\nlatency (ms)", "Search iters\nper decision", "Moves\nper game"]
    bars = ax.bar(metric_names, metrics, color=["#5E5CFF", "#7E3CFF", "#26C9FF"])
    for r, v in zip(bars, metrics):
        ax.text(r.get_x() + r.get_width() / 2, r.get_height(),
                f"{v:.1f}", ha="center", va="bottom", fontsize=9)
    ax.set_title("Per-game agent telemetry")
    ax.set_ylim(0, max(metrics) * 1.2 + 1)

    plt.tight_layout()
    fig.savefig(FIG / "head_to_head.png", bbox_inches="tight")
    fig.savefig(FIG / "head_to_head.svg", bbox_inches="tight")
    plt.close(fig)
    print("  saved head_to_head.png/svg")


def fig_mcts_position_quality():
    p = ROOT / "csv" / "mcts_position_quality.json"
    if not p.exists():
        print("  mcts_position_quality.json not present yet — skipping")
        return
    data = json.loads(p.read_text())["positions"]
    if not data:
        return
    fig, ax = plt.subplots(figsize=(8, 4))
    x = [f"pos {d['position']}" for d in data]
    iters_per_s = [d["iters_per_sec"] for d in data]
    branching = [d["branching_factor"] for d in data]
    ax.bar(x, iters_per_s, color="#5E5CFF", label="MCTS iter/s")
    ax2 = ax.twinx()
    ax2.plot(x, branching, color="#FF647C", marker="o", linewidth=2,
             label="branching factor")
    ax.set_ylabel("iterations/s")
    ax2.set_ylabel("branching factor")
    ax.set_title("MCTS search quality per opening position")
    fig.legend(loc="upper right", bbox_to_anchor=(0.95, 0.95))
    plt.tight_layout()
    fig.savefig(FIG / "mcts_position_quality.png", bbox_inches="tight")
    plt.close(fig)
    print("  saved mcts_position_quality.png")


def fig_deck_candidates():
    p = ROOT / "csv" / "deck_candidates.csv"
    if not p.exists():
        print("  deck_candidates.csv not present yet — skipping")
        return
    import csv
    rows = list(csv.DictReader(p.open(encoding="utf-8")))
    if not rows:
        return
    fig, ax = plt.subplots(figsize=(8, 4))
    labels = [f'{r["archetype"]}#{r["candidate_idx"]}' for r in rows]
    scores = [float(r["builder_score"]) for r in rows]
    synergy = [float(r["synergy_score"]) for r in rows]
    x = range(len(rows))
    width = 0.4
    ax.bar([i - width / 2 for i in x], scores, width, label="builder score", color="#5E5CFF")
    ax.bar([i + width / 2 for i in x], synergy, width, label="synergy score", color="#FFB623")
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, rotation=20)
    ax.set_title("Deck candidates — builder vs analyzer synergy")
    ax.legend()
    plt.tight_layout()
    fig.savefig(FIG / "deck_candidates.png", bbox_inches="tight")
    plt.close(fig)
    print("  saved deck_candidates.png")


def fig_architecture():
    """Layered architecture diagram (no measured data — block schematic)."""
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.axis("off")
    layers = [
        ("Layer", "Module", "Role"),
        ("FastAPI / CLI", "src/server, src/cli", "HTTP & CLI surface"),
        ("Competition agent", "src/competition", "Pure inference, no training deps"),
        ("MCTS", "src/mcts", "PUCT + transposition + LRU inference cache"),
        ("Neural net (optional)", "src/mcts/network.py", "ResNet policy+value head"),
        ("Heuristic evaluator", "src/mcts/evaluator.py", "Fallback when no checkpoint"),
        ("Simulator (engine)", "src/simulator", "Full TCG rules — 1.0 fidelity in tests"),
        ("Game state + encoder", "src/game_state", "Immutable state + 741-d features"),
        ("Card layer", "src/cards", "1,267 cards, effect parser, relationship graph"),
        ("Deck tooling", "src/decks, src/deck_builder", "Analyzer + genetic builder"),
    ]
    n = len(layers)
    cell_h = 0.7
    cell_widths = [2.6, 3.4, 4.0]
    x0 = 0.2
    y = n * cell_h
    palette = ["#23223A", "#5E5CFF", "#7E3CFF", "#26C9FF", "#00C49F",
               "#FFB623", "#FF647C", "#9966FF", "#6699FF", "#BB66FF"]
    for i, row in enumerate(layers):
        is_header = (i == 0)
        for j, txt in enumerate(row):
            x = x0 + sum(cell_widths[:j])
            ax.add_patch(plt.Rectangle(
                (x, y - cell_h), cell_widths[j], cell_h,
                facecolor=palette[i if not is_header else 0],
                edgecolor="white", linewidth=2, alpha=0.95,
            ))
            ax.text(x + cell_widths[j] / 2, y - cell_h / 2, txt,
                    ha="center", va="center",
                    color="white", fontsize=9,
                    fontweight="bold" if is_header else "normal")
        y -= cell_h
    ax.set_xlim(0, x0 + sum(cell_widths) + 0.5)
    ax.set_ylim(-0.5, n * cell_h + 0.5)
    ax.set_title("System architecture — top to bottom", fontsize=12, pad=10)
    plt.tight_layout()
    fig.savefig(FIG / "architecture.png", bbox_inches="tight")
    fig.savefig(FIG / "architecture.svg", bbox_inches="tight")
    plt.close(fig)
    print("  saved architecture.png/svg")


def fig_simulator_validation():
    """From the n=20 simulator-validation run earlier."""
    data = {
        "trainer_executions": {
            "Accompanying Flute": 16, "Prime Catcher": 15, "Hand Trimmer": 15,
            "Bug Catching Set": 14, "Roto-Stick": 14, "Buddy-Buddy Poffin": 14,
            "Enhanced Hammer": 12, "Scoop Up Cyclone": 11, "Rare Candy": 11,
            "Awakening Drum": 10, "Hole-Digging Shovel": 10, "Love Ball": 9,
            "Unfair Stamp": 9, "Boxed Order": 9, "Hyper Aroma": 8,
            "Secret Box": 6, "Ogre's Mask": 6, "Reboot Pod": 5,
        },
        "attack_executions": {
            "Ball Roll": 4, "Find a Friend": 3, "Mirror Attack": 3,
            "Comet Punch": 2, "Wicked Impact": 2, "Dual Headbutt": 2,
            "Ground Crasher": 1, "Hex Hurl": 1,
        },
    }
    fig, axes = plt.subplots(1, 2, figsize=(11, 5))
    for ax, (title, items, color) in zip(
        axes,
        [
            ("Top trainer cards executed (n=20 games)",
             list(data["trainer_executions"].items()), "#5E5CFF"),
            ("Attacks executed (n=20 games)",
             list(data["attack_executions"].items()), "#FF647C"),
        ],
    ):
        items = sorted(items, key=lambda kv: kv[1])
        names = [k for k, _ in items]
        counts = [v for _, v in items]
        ax.barh(names, counts, color=color)
        ax.set_title(title)
        ax.set_xlabel("executions")
    plt.tight_layout()
    fig.savefig(FIG / "simulator_validation.png", bbox_inches="tight")
    plt.close(fig)
    print("  saved simulator_validation.png")


if __name__ == "__main__":
    print("Generating figures...")
    fig_benchmarks()
    fig_simulator_validation()
    fig_architecture()
    fig_head_to_head()
    fig_mcts_position_quality()
    fig_deck_candidates()
    print("DONE")
