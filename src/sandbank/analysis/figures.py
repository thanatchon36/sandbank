"""Paper figures from ``results/aggregated/runs.csv`` (house style shared with the author's other papers).

Libertinus Serif (vendored in ``figures/fonts``), sized so 8 pt prints at 8 pt at the paper's text width;
no in-figure titles (panel labels only); one fixed colour per model (Okabe–Ito blue, vermillion and green,
checked for colour-vision deficiency and print contrast); every interval is Wilson 95%. Each figure is
written as PDF (paper) and 300-dpi PNG (README).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import font_manager
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.lines import Line2D

from sandbank.analysis.summary import wilson

ROOT = Path(__file__).resolve().parents[3]
FONT_DIR = ROOT / "figures" / "fonts"
INK, MUTED, GRID = "#1a1a1a", "#5a5a5a", "#e3e3e3"
MODEL = {"haiku": "#0072B2", "sonnet": "#D55E00", "opus": "#009E73"}  # Okabe–Ito, fixed per model
NAME = {"haiku": "Haiku 5.5", "sonnet": "Sonnet 5.5", "opus": "Opus 5.5"}
SHORT = {"haiku": "Haiku", "sonnet": "Sonnet", "opus": "Opus"}
WIDTH = 16.0 / 2.54  # A4, 2.5 cm margins
DOT = {"marker": "o", "ms": 4.5, "mec": "white", "mew": 0.7, "ls": "none"}  # white ring: marks never merge
PRESSURE = {
    "P0": "P0  no target",
    "P1": "P1  target stated",
    "P2": "P2  bonus and review at stake",
    "P3": "P3  branch closure, roles cut",
}
Mask = Callable[[pd.DataFrame], pd.Series]
# Every confirmatory cell outside Experiment A, in pre-registration order; P3 and soft controls unless stated.
CELLS: list[tuple[str, str, Mask]] = [
    ("B", "B · Policy-only controls (H0)", lambda d: (d.experiment == "B") & (d.hardness == "H0")),
    ("B", "B · Hard controls (H2)", lambda d: (d.experiment == "B") & (d.hardness == "H2")),
    ("C", "C · Audit cue (O1)", lambda d: (d.experiment == "C") & (d.oversight == "O1")),
    ("C", "C · Reviews paused (O2)", lambda d: (d.experiment == "C") & (d.oversight == "O2")),
    ("D", "D · Compliance sentence, P1", lambda d: (d.experiment == "D") & (d.pressure == "P1")),
    ("D", "D · Compliance sentence, P2", lambda d: (d.experiment == "D") & (d.pressure == "P2")),
    ("D", "D · Compliance sentence, P3", lambda d: (d.experiment == "D") & (d.pressure == "P3")),
    ("E", "E · M1 rulebook summary", lambda d: (d.experiment == "E") & (d.mitigation == "M1")),
    ("E", "E · M3 target extension", lambda d: (d.experiment == "E") & (d.mitigation == "M3")),
    ("E", "E · M4 written justification", lambda d: (d.experiment == "E") & (d.mitigation == "M4")),
    ("E", "E · M6 hard controls + extension", lambda d: (d.experiment == "E") & (d.mitigation == "M6")),
    ("F", "F · Compliance-only floor", lambda d: (d.experiment == "F") & (d.frame == "floor")),
    ("F", "F · P4 explicit licence", lambda d: (d.experiment == "F") & (d.frame == "sales")),
    ("G", "G · Five-day episode, P3", lambda d: (d.experiment == "G") & (d.pressure == "P3")),
    ("G", "G · Five-day episode, P0", lambda d: (d.experiment == "G") & (d.pressure == "P0")),
]


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
            "xtick.major.size": 2.5,
            "ytick.major.size": 2.5,
            "xtick.color": "#3a3a3a",
            "ytick.color": "#3a3a3a",
            "xtick.labelcolor": INK,
            "ytick.labelcolor": INK,
            "text.color": INK,
            "axes.labelcolor": INK,
            "legend.frameon": False,
            "legend.handlelength": 1.6,
            "legend.handletextpad": 0.5,
            "legend.columnspacing": 1.6,
            "pdf.fonttype": 42,
        }
    )


def save(fig: Figure, out: Path, name: str) -> None:
    out.mkdir(parents=True, exist_ok=True)
    fig.savefig(out / f"{name}.pdf", bbox_inches="tight", pad_inches=0.02)
    fig.savefig(out / f"{name}.png", dpi=300, bbox_inches="tight", pad_inches=0.04)
    plt.close(fig)


def panel(ax: Axes, letter: str, text: str | None = None, x: float = 0.0, lines: int = 1) -> None:
    """Panel letter (bold) and, for small multiples, the facet's name beside it; top-aligned so that
    one- and two-line names sit at the same height across panels."""
    dy = 4 + 10 * lines
    ax.annotate(
        letter,
        (x, 1.0),
        xycoords="axes fraction",
        xytext=(0, dy),
        textcoords="offset points",
        ha="left",
        va="top",
        fontsize=9,
        weight="bold",
    )
    if text:
        ax.annotate(
            text,
            (x, 1.0),
            xycoords="axes fraction",
            xytext=(15, dy),
            textcoords="offset points",
            ha="left",
            va="top",
            fontsize=8,
            linespacing=1.15,
        )


def models(df: pd.DataFrame) -> list[str]:
    return [m for m in MODEL if m in set(df.model)]


def model_legend(fig: Figure, ms: list[str], y: float, x: float = 0.5) -> None:
    """One legend for the whole figure, above the panels: a line through a dot, one entry per model."""
    if not ms:
        return
    handles = [Line2D([], [], color=MODEL[m], lw=1.6, **{**DOT, "ls": "-"}) for m in ms]
    fig.legend(handles, [NAME[m] for m in ms], loc="lower center", bbox_to_anchor=(x, y), ncol=len(ms))


def above(fig: Figure, ax: Axes, points: float) -> float:
    """Figure-fraction y of a point ``points`` above the top of ``ax`` (for a legend over panel labels)."""
    return ax.get_position().y1 + points / 72 / fig.get_figheight()


def interval(
    ax: Axes, k: int, n: int, colour: str, *, y: float | None = None, x: float | None = None
) -> None:
    """Observed rate (dot) and Wilson 95% interval (line), horizontal at ``y`` or vertical at ``x``."""
    lo, hi = wilson(k, n)
    rate = 100 * k / n
    if y is not None:
        ax.plot([100 * lo, 100 * hi], [y, y], color=colour, lw=1.6, solid_capstyle="butt", zorder=2)
        ax.plot([rate], [y], color=colour, zorder=3, **DOT)
    else:
        ax.plot([x, x], [100 * lo, 100 * hi], color=colour, lw=1.6, solid_capstyle="butt", zorder=2)
        ax.plot([x], [rate], color=colour, zorder=3, **DOT)


def forest_axes(ax: Axes, xmax: float) -> None:
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0, pad=6)
    ax.grid(False, axis="y")
    ax.grid(True, axis="x", color=GRID, lw=0.6)
    ax.set_xlim(-0.025 * xmax, xmax)


def fig_bounds(df: pd.DataFrame, out: Path) -> None:
    """Forest plot of the violation rate per condition: (a) Experiment A by pressure, the three models
    within each row; (b) every other confirmatory cell, with violations / runs in the right column."""
    left, right = 0.34, 0.90
    fig, (a, b) = plt.subplots(
        2, 1, figsize=(WIDTH, 4.3), gridspec_kw={"height_ratios": [6.2, 18.4], "hspace": 0.38}
    )
    fig.subplots_adjust(left=left, right=right, top=0.945, bottom=0.065)
    x_letter = -left / (right - left)  # the figure's left edge, in axes fraction

    A = df[df.experiment == "A"]
    ms = models(A)
    ps = sorted(A.pressure.unique())
    his = []
    for r, p in enumerate(ps):
        for i, m in enumerate(ms):
            g = A[(A.model == m) & (A.pressure == p)]
            k, n = int(g.violated.sum()), len(g)
            interval(a, k, n, MODEL[m], y=-r - (i - (len(ms) - 1) / 2) * 0.3)
            his.append(wilson(k, n)[1])
    a.set_yticks([-r for r in range(len(ps))], [PRESSURE.get(p, p) for p in ps])
    a.set_ylim(-(len(ps) - 1) - 0.6, 0.6)
    forest_axes(a, 100 * max(his, default=0.05) * 1.12)
    per_level = ", ".join(f"{SHORT[m]} {A[(A.model == m) & (A.pressure == ps[0])].shape[0]}" for m in ms)
    a.set_xlabel("Violation rate, %" + (f" (runs per pressure level: {per_level})" if ps else ""))
    panel(a, "(a)", x=x_letter)

    rest = df[df.experiment != "A"]
    y, prev, ticks, labels, his = 0.0, "", [], [], []
    for exp, label, mask in CELLS:
        if prev and exp != prev:
            y -= 0.6
        prev = exp
        g = rest[mask(rest)]
        gm = models(g)
        counts = []
        for i, m in enumerate(gm):
            gg = g[g.model == m]
            k, n = int(gg.violated.sum()), len(gg)
            interval(b, k, n, MODEL[m], y=y - (i - (len(gm) - 1) / 2) * 0.3)
            counts.append((k, n))
            his.append(wilson(k, n)[1])
        if len(set(counts)) == 1:
            text = f"{counts[0][0]} / {counts[0][1]}" + (" each" if len(counts) > 1 else "")
        else:
            text = " · ".join(f"{k} / {n}" for k, n in counts)
        b.text(
            1.02,
            y,
            text,
            transform=b.get_yaxis_transform(),
            ha="left",
            va="center",
            fontsize=7.5,
            color=MUTED,
        )
        ticks.append(y)
        labels.append(label)
        y -= 1
    b.text(
        1.02,
        1.0,
        "violations / runs",
        transform=b.transAxes,
        ha="left",
        va="bottom",
        fontsize=7.5,
        color=MUTED,
    )
    b.set_yticks(ticks, labels)
    b.set_ylim(y + 1 - 0.6, 0.6)
    forest_axes(b, 100 * max(his, default=0.05) * 1.08)
    b.set_xlabel("Violation rate, % (dot: observed; line: 95% Wilson interval)")
    panel(b, "(b)", x=x_letter)
    model_legend(fig, ms, 0.955, x=(left + right) / 2)
    save(fig, out, "fig1_bounds")


def fig_behaviour(df: pd.DataFrame, out: Path) -> None:
    """Share of Experiment A runs in which the agent took each compliant action, by pressure and model."""
    A = df[df.experiment == "A"]
    acts = [
        ("checked_kyc", "Ran the KYC check\non the blocked customer"),
        ("requested_docs", "Requested documents"),
        ("escalated_compliance", "Escalated to Compliance"),
        ("told_manager", "Told the manager a lead\nwould not convert"),
    ]
    fig, axes = plt.subplots(1, len(acts), figsize=(WIDTH, 2.25), sharey=True)
    ps = sorted(A.pressure.unique())
    x = np.arange(len(ps))
    for ax, (col, lab), tag in zip(axes, acts, "abcd", strict=True):
        for m in models(A):
            ys = [100 * A[(A.model == m) & (A.pressure == p)][col].mean() for p in ps]
            ax.plot(x, ys, color=MODEL[m], lw=1.1, label=NAME[m], **{**DOT, "ls": "-", "ms": 4})
        ax.set_xticks(x, ps)
        ax.set_xlim(-0.4, len(ps) - 0.6)
        ax.set_ylim(0, 104)
        ax.set_yticks([0, 25, 50, 75, 100])
        panel(ax, f"({tag})", lab, lines=2)
    axes[0].set_ylabel("Runs, %")
    fig.supxlabel("Pressure (Experiment A)", fontsize=8.5)
    fig.tight_layout(w_pad=1.2, rect=(0, 0, 1, 0.86))
    model_legend(fig, models(A), above(fig, axes[0], 30))
    save(fig, out, "fig2_behaviour")


def fig_goal(df: pd.DataFrame, out: Path) -> None:
    """Goal attainment that policy allows: the B4 large deposit opened with its report filed, by pressure
    and model (Experiment A), with the four levels pooled at the right. The clean lead converted in every
    run, so it is not plotted."""
    A = df[(df.experiment == "A") & (df.lead == "B4")]
    ps = sorted(A.pressure.unique())
    ms = models(A)
    groups = [(p, A[A.pressure == p]) for p in ps] + [("P0–P3\npooled", A)]
    xs = [float(i) for i in range(len(ps))] + [len(ps) + 0.6]
    fig, ax = plt.subplots(figsize=(WIDTH * 0.6, 2.4))
    for (_, g), xg in zip(groups, xs, strict=True):
        for i, m in enumerate(ms):
            gm = g[g.model == m]
            interval(ax, int(gm.converted.sum()), len(gm), MODEL[m], x=xg + (i - (len(ms) - 1) / 2) * 0.24)
    ax.axvline(len(ps) - 0.2, color=GRID, lw=0.8, zorder=1)
    ax.set_xticks(xs, [p for p, _ in groups])
    ax.set_xlim(-0.5, xs[-1] + 0.5)
    ax.set_ylim(0, 103)
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.set_ylabel("B4 opened with its report, %")
    ax.set_xlabel("Pressure (Experiment A)")
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    model_legend(fig, ms, above(fig, ax, 6))
    save(fig, out, "fig3_goal")


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
    return sorted(p.name for p in out.glob("*.pdf"))
