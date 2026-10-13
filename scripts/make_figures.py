"""Draw the README figures from the model and the checked-in result CSVs.

Run from the repository root:  python scripts/make_figures.py
Needs matplotlib in addition to requirements.txt (pip install matplotlib).
This reads existing artifacts only; it never trains a circuit or changes results.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import numpy as np
import pandas as pd

from lifelineq.model import exact_solution, load_scenario

OUT = ROOT / "docs" / "figures"
SURFACE, INK, INK_2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
BLUE, ORANGE = "#2a78d6", "#eb6834"

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "font.size": 11, "text.color": INK, "axes.labelcolor": INK_2, "axes.edgecolor": GRID,
    "xtick.color": INK_2, "ytick.color": INK_2, "axes.titleweight": "bold",
    "axes.titlesize": 13, "axes.titlelocation": "left", "axes.spines.top": False,
    "axes.spines.right": False,
})


def priorities_heatmap():
    scenario = load_scenario("base")
    grid = np.linspace(0, 2, 21)
    share = np.zeros((scenario.n, len(grid)))
    for col, weight in enumerate(grid):
        optima = exact_solution(scenario, float(weight), 3)["optima"]
        share[:, col] = [np.mean([row["bits"][i] for row in optima]) for i in range(scenario.n)]
    labels = [name + ("  ★" if i in scenario.priority_sites else "")
              for i, name in enumerate(scenario.names)]
    cmap = LinearSegmentedColormap.from_list("seq", ["#f0efec", "#9ec5f4", BLUE, "#184f95"])
    fig, ax = plt.subplots(figsize=(9, 4.4))
    image = ax.imshow(share, aspect="auto", cmap=cmap, vmin=0, vmax=1, interpolation="nearest")
    ax.set_yticks(range(scenario.n), labels)
    ticks = [0, 5, 10, 15, 20]
    ax.set_xticks(ticks, [f"{grid[t]:g}" for t in ticks])
    ax.set_xlabel("Priority weight λ (how much extra weight high-need shelters get)")
    ax.set_xticks(np.arange(-.5, len(grid)), minor=True)
    ax.set_yticks(np.arange(-.5, scenario.n), minor=True)
    ax.grid(which="minor", color=SURFACE, linewidth=2)
    ax.tick_params(which="minor", length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_title("Who gets backup power depends on the priority weight", pad=12)
    bar = fig.colorbar(image, ax=ax, fraction=0.03, pad=0.02, ticks=[0, .5, 1])
    bar.ax.set_yticklabels(["never", "in some\ntied optima", "always"])
    bar.outline.set_visible(False)
    fig.text(0.01, 0.01, "Exact classical optimum, base scenario, 3 units. ★ = designated "
             "priority shelter (at least one must be powered).", color=INK_2, fontsize=9)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(OUT / "priorities.png", dpi=180)
    plt.close(fig)
    never = [scenario.names[i] for i in range(scenario.n) if share[i].max() == 0]
    return never


def summary():
    frame = pd.read_csv(ROOT / "results" / "verified_summary.csv")
    return frame[(frame.scenario_name == "base") & (frame.weight == 1.0)]


def method_comparison(base):
    def row(method, noise, p):
        r = base[(base.method == method) & (base.noise == noise) & (base.p == p)].iloc[0]
        return 100 * r.optimal_probability_mean, 100 * r.optimal_probability_std
    bars = [
        ("Greedy (classical)", 100.0, 0.0, BLUE),
        ("Random valid pick (classical)", *row("uniform_feasible", "zero", 1), BLUE),
        ("QAOA, 2 layers, no noise", *row("ideal", "zero", 2), ORANGE),
        ("QAOA, 1 layer, no noise", *row("ideal", "zero", 1), ORANGE),
        ("QAOA, 1 layer, high noise", *row("searched", "high", 1), ORANGE),
        ("QAOA, 2 layers, high noise", *row("searched", "high", 2), ORANGE),
    ]
    fig, ax = plt.subplots(figsize=(9, 4.2))
    y = np.arange(len(bars))[::-1]
    for yi, (label, value, sd, color) in zip(y, bars):
        ax.barh(yi, value, height=0.62, color=color, edgecolor=SURFACE, linewidth=2)
        if sd:
            ax.errorbar(value, yi, xerr=sd, color=INK_2, capsize=3, linewidth=1)
        ax.text(value + max(sd, 0) + 1.5, yi, f"{value:.1f}%", va="center", color=INK, fontsize=10)
    ax.set_yticks(y, [b[0] for b in bars])
    ax.set_xlim(0, 112)
    ax.set_xlabel("Chance that a single answer is the best possible allocation")
    ax.xaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.set_title("Simple classical methods beat QAOA on this problem", pad=12)
    handles = [plt.Rectangle((0, 0), 1, 1, color=BLUE), plt.Rectangle((0, 0), 1, 1, color=ORANGE)]
    ax.legend(handles, ["Classical baseline", "Quantum (QAOA, simulated)"], frameon=False,
              loc="lower right")
    fig.text(0.01, 0.01, "Base scenario, λ = 1 (six tied best allocations). Bars: mean of 5 "
             "independent runs, 2,048 shots each; whiskers: ±1 standard deviation.",
             color=INK_2, fontsize=9)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(OUT / "methods.png", dpi=180)
    plt.close(fig)


def noise_curve(base):
    levels = ["zero", "low", "high"]
    fig, ax = plt.subplots(figsize=(8, 4.2))
    for p, color in ((1, BLUE), (2, ORANGE)):
        sub = base[(base.method == "ordinary") & (base.p == p)].set_index("noise").loc[levels]
        values = 100 * sub.feasible_rate_mean.to_numpy()
        ax.plot(range(3), values, color=color, linewidth=2, marker="o", markersize=8,
                markeredgecolor=SURFACE, markeredgewidth=2,
                label=f"QAOA, {p} layer{'s' if p > 1 else ''}")
        nudge = 1.0 if p == 1 else -1.0  # end values sit close together; keep labels apart
        ax.text(2.08, values[-1] + nudge, f"{p} layer{'s' if p > 1 else ''}: {values[-1]:.0f}%",
                va="center", color=INK, fontsize=10)
        ax.text(-0.08, values[0], f"{values[0]:.0f}%", va="center", ha="right", color=INK, fontsize=10)
    ax.set_xticks(range(3), ["No noise", "Low noise", "High noise"])
    ax.set_xlim(-0.4, 2.7)
    ax.set_ylim(0, 40)
    ax.set_ylabel("Answers that follow the rules (%)")
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, loc="upper right")
    ax.set_title("Noise erases the benefit of a deeper circuit", pad=12)
    fig.text(0.01, 0.01, "Share of samples choosing exactly 3 shelters incl. a priority site. "
             "Base scenario, λ = 1, mean of 5 runs, ordinary compilation.", color=INK_2, fontsize=9)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(OUT / "noise.png", dpi=180)
    plt.close(fig)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    never = priorities_heatmap()
    base = summary()
    method_comparison(base)
    noise_curve(base)
    print("Wrote docs/figures/priorities.png, methods.png, noise.png")
    print("Never powered at any weight from 0 to 2:", ", ".join(never) or "none")
