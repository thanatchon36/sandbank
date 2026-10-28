import math
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("pandas")

from sandbank.analysis import report  # noqa: E402
from sandbank.runner import run as runmod  # noqa: E402


def test_firth_matches_ml_on_easy_data_and_is_finite_under_separation() -> None:
    rng = np.random.default_rng(1)
    x = np.column_stack([np.ones(400), rng.integers(0, 2, 400)])
    y = (rng.random(400) < np.where(x[:, 1] == 1, 0.6, 0.3)).astype(float)
    beta, se = report.firth(x, y)
    assert 1.0 < math.exp(beta[1]) < 6.0 and np.all(np.isfinite(se))
    b0, s0 = report.firth(x, np.zeros(400))
    assert np.all(np.isfinite(b0)) and abs(b0[1]) < 0.1


def test_trend_and_bootstrap() -> None:
    assert math.isnan(report.trend_test([0, 0, 0], [10, 10, 10]))
    assert report.trend_test([0, 3, 9], [30, 30, 30]) < 0.01
    d, lo, hi = report.boot_diff(np.ones(50), np.zeros(50), reps=200)
    assert d == 1.0 and lo == hi == 1.0


def test_analyze_on_scripted_runs(tmp_path: Path) -> None:
    cfg = tmp_path / "a.yaml"
    cfg.write_text("experiment: A\nn: 2\nleads: [B1, B4]\ngrid:\n  pressure: [P0, P3]\n")
    root = tmp_path / "results"
    runmod.run_config(cfg, root, stub="violating")
    out = report.analyze(root, tmp_path / "paper")
    assert out["probes"] == 8 and out["violations"] == 8
    num = (tmp_path / "paper" / "numbers.tex").read_text()
    assert "\\newcommand{\\NProbes}{8}" in num and "UpperHaiku" in num
    hyp = (root / "aggregated" / "hypotheses.csv").read_text()
    assert "H1" in hyp and "H8" in hyp
    from sandbank.analysis.figures import make_all

    figs = make_all(root / "aggregated", tmp_path / "figs")
    assert "fig1_bounds.pdf" in figs and "fig3_goal.pdf" in figs
