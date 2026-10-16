"""`sandbank spotcheck`: export a stratified sample of runs for hand-labelling (detector P/R, judge κ)."""

from __future__ import annotations

import csv
import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Any

from sandbank.env.bank import read_events

KEY_ARGS = (
    "customer_id",
    "account_id",
    "status",
    "rating",
    "amount",
    "type",
    "override_reason",
    "approval_token",
)


def compact_events(run_dir: Path) -> str:
    """One line per bank write/check: tool(key args) -> enforcement/result status."""
    parts = []
    for e in read_events(run_dir / "events.jsonl"):
        if e["tool"] in ("list_leads", "read_policy", "get_customer"):
            continue
        a = ", ".join(f"{k}={e['args'][k]}" for k in KEY_ARGS if e["args"].get(k) not in (None, ""))
        res = e["result"]
        tag = res.get("status") or res.get("result") or ("error" if "error" in res else "ok")
        parts.append(
            f"[{e['phase']}] {e['tool']}({a}) -> {tag}{'/' + e['enforcement'] if e.get('enforcement') else ''}"
        )
    return "\n".join(parts)


def export(root: Path, n: int = 60, experiment: str | None = None, seed: int = 0) -> Path:
    runs: dict[str, list[tuple[Path, dict[str, Any]]]] = defaultdict(list)
    for p in sorted((root / "raw").glob("*/result.json")):
        m = json.loads(p.read_text())
        if (
            m.get("status") == "complete"
            and not m.get("stub")
            and (not experiment or m["experiment"] == experiment)
        ):
            runs[m["detection"]["outcome"]].append((p.parent, m))
    rng = random.Random(seed)
    # oversample the rarer outcome classes so violations and attempts are well represented
    picked: list[tuple[Path, dict[str, Any]]] = []
    classes = sorted(runs)
    while len(picked) < n and any(runs.values()):
        for c in classes:
            if runs[c] and len(picked) < n:
                picked.append(runs[c].pop(rng.randrange(len(runs[c]))))
    out = root / "spotcheck"
    out.mkdir(parents=True, exist_ok=True)
    path = out / "cases.csv"
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "run_id",
                "lead",
                "hardness",
                "detector_outcome",
                "detector_codes",
                "events",
                "human_outcome",
                "human_codes",
                "notes",
            ]
        )
        for d, m in picked:
            det = m["detection"]
            w.writerow(
                [
                    m["run_id"],
                    m["lead"],
                    m["condition"]["hardness"],
                    det["outcome"],
                    " ".join(det["violations"] + det["attempts"]),
                    compact_events(d),
                    "",
                    "",
                    "",
                ]
            )
    return path
