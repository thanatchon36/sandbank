"""Paper figures from ``results/aggregated/runs.csv`` (house style shared with the author's other papers).

Libertinus Serif (vendored in ``figures/fonts``), sized so 8 pt prints at 8 pt at the paper's text width;
no in-figure titles (panel labels only); one fixed colour per model; an ordinal blue ramp for pressure.
Each figure is written as PDF (paper) and 300-dpi PNG (README).
"""

from __future__ import annotations

from pathlib import Path

import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import font_manager
from matplotlib.axes import Axes
from matplotlib.figure import Figure

from sandbank.analysis.summary import wilson

ROOT = Path(__file__).resolve().parents[3]
FONT_DIR = ROOT / "figures" / "fonts"
INK, MUTED, GRID = "#1a1a1a", "#5a5a5a", "#e6e6e6"
MODEL = {"haiku": "#0072B2", "sonnet": "#E69F00", "opus": "#009E73"}  # Okabe-Ito, fixed per model
NAME = {"haiku": "Haiku 5.5", "sonnet": "Sonnet 5.5", "opus": "Opus 5.5"}
BLUE_RAMP = ("#c6dbef", "#9ecae1", "#6baed6", "#3182bd", "#08519c", "#08306b")
WIDTH = 16.0 / 2.54  # A4, 2.5 cm margins


def setup() -> None:
    for p in sorted(FONT_DIR.glob("LibertinusSerif-*.otf")):
        font_manager.fontManager.addfont(str(p))
    plt.rcParams.update(
        {
            "font.family": "Libertinus Serif",
            "font.size": 8.5,
            "axes.labelsize": 8.5,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "legend.fontsize": 8,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.linewidth": 0.6,
            "axes.edgecolor": "#3a3a3a",
            "axes.grid": True,
            "axes.grid.axis": "y",
            "grid.color": GRID,
            "grid.linewidth": 0.6,
            "axes.axisbelow": True,
            "text.color": INK,
            "axes.labelcolor": INK,
            "pdf.fonttype": 42,
            "legend.frameon": False,
        }
    )


def save(fig: Figure, out: Path, name: str) -> None:
    out.mkdir(parents=True, exist_ok=True)
    fig.savefig(out / f"{name}.pdf", bbox_inches="tight")
    fig.savefig(out / f"{name}.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def panel(ax: Axes, label: str) -> None:
    ax.text(-0.02, 1.06, label, transform=ax.transAxes, ha="right", va="bottom", fontsize=9, weight="bold")


def models(df: pd.DataFrame) -> list[str]:
    return [m for m in MODEL if m in set(df.model)]


def fig_bounds(df: pd.DataFrame, out: Path) -> None:
    """(a) Experiment A: observed violation rate and Wilson 95% interval by pressure and model.
    (b) Every other experiment cell, pooled over leads."""
    fig, (a, b) = plt.subplots(1, 2, figsize=(WIDTH, 2.5), gridspec_kw={"width_ratios": [1, 1.5]})
    A = df[df.experiment == "A"]
    ms = models(A)
    for i, m in enumerate(ms):
        for j, p in enumerate(sorted(A.pressure.unique())):
            g = A[(A.model == m) & (A.pressure == p)]
            k, n = int(g.violated.sum()), len(g)
            lo, hi = wilson(k, n)
            x = j + (i - (len(ms) - 1) / 2) * 0.22
            a.plot([x, x], [100 * lo, 100 * hi], color=MODEL[m], lw=2, solid_capstyle="butt")
            a.plot(x, 100 * k / n, "o", color=MODEL[m], ms=3.5, label=NAME[m] if j == 0 else None)
    a.set_xticks(range(A.pressure.nunique()), sorted(A.pressure.unique()))
    a.set_ylabel("Violation rate, % (95% CI)")
    a.set_xlabel("Pressure (Experiment A)")
    a.set_ylim(bottom=0)
    a.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=len(ms), handlelength=1)
    panel(a, "(a)")

    rest = df[df.experiment != "A"].copy()
    rest["cell"] = rest.apply(_cell_label, axis=1)
    order = list(dict.fromkeys(rest.sort_values(["experiment", "cell"]).cell))
    for j, c in enumerate(order):
        for i, m in enumerate(models(rest)):
            g = rest[(rest.cell == c) & (rest.model == m)]
            if g.empty:
                continue
            k, n = int(g.violated.sum()), len(g)
            lo, hi = wilson(k, n)
            x = j + (i - 0.5) * 0.25 if rest[rest.cell == c].model.nunique() > 1 else j
            b.plot([x, x], [100 * lo, 100 * hi], color=MODEL[m], lw=2, solid_capstyle="butt")
            b.plot(x, 100 * k / n, "o", color=MODEL[m], ms=3.5)
    b.set_xticks(range(len(order)), order, rotation=60, ha="right", rotation_mode="anchor")
    b.set_ylim(bottom=0)
    b.set_ylabel("Violation rate, % (95% CI)")
    panel(b, "(b)")
    fig.tight_layout()
    save(fig, out, "fig1_bounds")


def _cell_label(r: pd.Series) -> str:
    e = r.experiment
    if e == "B":
        return f"B {r.hardness}"
    if e == "C":
        return f"C {r.oversight}"
    if e == "D":
        return f"D C+ {r.pressure}"
    if e == "E":
        return f"E {r.mitigation}"
    if e == "F":
        return "F floor" if r.frame == "floor" else "F P4"
    if e == "G":
        return f"G {r.pressure} (5 days)"
    return str(e)


def fig_behaviour(df: pd.DataFrame, out: Path) -> None:
    """Share of Experiment A probes in which the agent took each compliant action, by pressure and model."""
    A = df[df.experiment == "A"]
    acts = [
        ("checked_kyc", "Ran the KYC check\non the blocked customer"),
        ("requested_docs", "Requested documents"),
        ("escalated_compliance", "Escalated to Compliance"),
        ("told_manager", "Told the manager"),
    ]
    fig, axes = plt.subplots(1, len(acts), figsize=(WIDTH, 2.1), sharey=True)
    ps = sorted(A.pressure.unique())
    for ax, (col, lab), tag in zip(axes, acts, "abcd", strict=True):
        for m in models(A):
            ys = [100 * A[(A.model == m) & (A.pressure == p)][col].mean() for p in ps]
            ax.plot(range(len(ps)), ys, "-o", color=MODEL[m], ms=3, lw=1.2, label=NAME[m])
        ax.set_xticks(range(len(ps)), ps)
        ax.set_ylim(0, 105)
        ax.set_xlabel(lab, fontsize=8)
        panel(ax, f"({tag})")
    axes[0].set_ylabel("Probes, %")
    axes[0].legend(loc="lower left", bbox_to_anchor=(0, 1.08), ncol=3, handlelength=1.2)
    fig.tight_layout()
    save(fig, out, "fig2_behaviour")


def fig_goal(df: pd.DataFrame, out: Path) -> None:
    """Goal attainment that policy allows: (a) the B4 large deposit opened with its report filed,
    (b) the clean lead converted, by pressure and model (Experiment A)."""
    A = df[df.experiment == "A"]
    ps = sorted(A.pressure.unique())
    fig, (a, b) = plt.subplots(1, 2, figsize=(WIDTH * 0.75, 2.2), sharey=True)
    for ax, sub, col, tag, lab in (
        (a, A[A.lead == "B4"], "converted", "(a)", "B4 large deposit opened\n(with its report)"),
        (b, A, "clean_converted", "(b)", "Clean lead converted"),
    ):
        w = 0.8 / len(models(sub))
        for i, m in enumerate(models(sub)):
            ys = [100 * sub[(sub.model == m) & (sub.pressure == p)][col].mean() for p in ps]
            ax.bar(
                np.arange(len(ps)) + (i - (len(models(sub)) - 1) / 2) * w,
                ys,
                w * 0.95,
                color=MODEL[m],
                label=NAME[m],
            )
        ax.set_xticks(range(len(ps)), ps)
        ax.set_ylim(0, 105)
        ax.set_xlabel(lab, fontsize=8)
        panel(ax, tag)
    a.set_ylabel("Probes, %")
    a.legend(loc="lower left", bbox_to_anchor=(0, 1.08), ncol=3, handlelength=1)
    fig.tight_layout()
    save(fig, out, "fig3_goal")


def fig_mitigations(mit: pd.DataFrame, out: Path) -> None:
    """Experiment E: clean-lead conversion difference vs no mitigation (bootstrap 95% CI) and mean turns."""
    fig, (a, b) = plt.subplots(1, 2, figsize=(WIDTH * 0.75, 2.0))
    m = mit[mit.mitigation != "none"].reset_index(drop=True)
    y = np.arange(len(m))
    a.errorbar(
        100 * m.conversion_diff_vs_none,
        y,
        xerr=[100 * (m.conversion_diff_vs_none - m.diff_lo), 100 * (m.diff_hi - m.conversion_diff_vs_none)],
        fmt="o",
        color=MODEL["haiku"],
        ms=3.5,
        lw=1.2,
        capsize=0,
    )
    a.axvline(0, color=MUTED, lw=0.6)
    a.set_yticks(y, m.mitigation)
    a.invert_yaxis()
    a.grid(axis="x")
    a.grid(axis="y", visible=False)
    a.set_xlabel("Clean-lead conversion vs none, pp")
    panel(a, "(a)")
    b.barh(np.arange(len(mit)), mit.mean_turns, color=[MUTED] + [MODEL["haiku"]] * len(m), height=0.6)
    b.set_yticks(np.arange(len(mit)), mit.mitigation)
    b.invert_yaxis()
    b.grid(axis="x")
    b.grid(axis="y", visible=False)
    b.set_xlabel("Mean agent turns per probe")
    panel(b, "(b)")
    fig.tight_layout()
    save(fig, out, "fig4_mitigations")


def make_all(agg: Path, out: Path) -> list[str]:
    setup()
    df = pd.read_csv(agg / "runs.csv")
    for col in (
        "violated",
        "attempted",
        "converted",
        "clean_converted",
        "checked_kyc",
        "requested_docs",
        "escalated_compliance",
        "told_manager",
    ):
        df[col] = df[col].astype(bool)
    fig_bounds(df, out)
    fig_behaviour(df, out)
    fig_goal(df, out)
    mit = pd.read_csv(agg / "mitigations.csv")
    if (mit.mitigation != "none").any():
        fig_mitigations(mit, out)
    return sorted(p.name for p in out.glob("*.pdf"))
