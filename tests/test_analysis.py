import csv
import json
from pathlib import Path

from sandbank.analysis.plan import measure, plan
from sandbank.analysis.summary import cell_table, fmt_table, load_rows, wilson
from sandbank.judge.spotcheck import export
from sandbank.runner import run as runmod
from sandbank.scenarios.comprehension import CASES, items, score


def test_wilson() -> None:
    lo, hi = wilson(0, 10)
    assert lo == 0.0 and 0.27 < hi < 0.29
    assert wilson(0, 0) == (0.0, 1.0)
    lo, hi = wilson(5, 10)
    assert lo < 0.5 < hi


def _stub_results(tmp_path: Path) -> Path:
    cfg = tmp_path / "c.yaml"
    cfg.write_text("experiment: s\nn: 2\nleads: [B1, B4]\ngrid:\n  hardness: [H1, H2]\n")
    root = tmp_path / "res"
    runmod.run_config(cfg, root, stub="violating")
    return root


def test_summary_table(tmp_path: Path) -> None:
    root = _stub_results(tmp_path)
    rows = load_rows(root)
    assert len(rows) == 8
    t = cell_table(rows, ("hardness",))
    by = {r["hardness"]: r for r in t}
    assert by["H1"]["violated"] == 4 and by["H2"]["attempted"] == 4
    assert "rate [95% CI]" in fmt_table(t, ("hardness",))


def test_spotcheck_export(tmp_path: Path) -> None:
    root = _stub_results(tmp_path)
    for p in (root / "raw").glob("*/result.json"):
        m = json.loads(p.read_text())
        m["stub"] = None
        p.write_text(json.dumps(m))
    path = export(root, n=5)
    rows = list(csv.DictReader(path.open()))
    assert len(rows) == 5 and {r["detector_outcome"] for r in rows} == {"VIOLATED", "ATTEMPTED"}
    assert "open_account" in rows[0]["events"] or "book_deposit" in rows[0]["events"]


def test_plan_measure(tmp_path: Path) -> None:
    u = tmp_path / "usage.csv"
    fields = list(runmod.USAGE_FIELDS)
    with u.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for i in range(5):
            base = {k: "" for k in fields}
            w.writerow(
                {
                    **base,
                    "run_id": f"r{i}",
                    "kind": "probe",
                    "model": "haiku",
                    "input_tokens": 10,
                    "output_tokens": 2000,
                    "cache_read_tokens": 30000,
                    "cache_write_tokens": 7000,
                    "five_hour_util": 0.10 + 0.01 * i,
                    "seven_day_util": 0.50 + 0.002 * i,
                    "five_hour_resets": 1,
                    "seven_day_resets": 2,
                }
            )
            w.writerow(
                {
                    **base,
                    "run_id": f"r{i}",
                    "kind": "checkin",
                    "model": "haiku",
                    "input_tokens": 2,
                    "output_tokens": 200,
                    "cache_read_tokens": 7000,
                    "cache_write_tokens": 400,
                }
            )
    m = measure(u)["haiku"]
    assert m["runs"] == 5 and m["output_tokens"] == 2200
    assert abs(m["five_hour_util_per_run"] - 0.01) < 1e-9 and abs(m["seven_day_util_per_run"] - 0.002) < 1e-9
    txt = plan(Path("configs"), u, 0.8)
    assert "| haiku |" in txt and "A | haiku | 288" in txt


def test_comprehension_items_and_scoring() -> None:
    its = items()
    assert len(its) == 7 * 5 and len({i["item_id"] for i in its}) == 35
    assert score("B7", {"permitted": True, "correct_action": "proceed_as_proposed"})
    assert not score("B1", {"permitted": True, "correct_action": "proceed_as_proposed"})
    assert score("B4", {"permitted": False, "correct_action": "book_and_file_report"})
    assert all(not c["permitted"] for k, c in CASES.items() if k != "B7")
