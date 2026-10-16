"""Lightweight per-cell summaries from results/ (no third-party deps)."""

from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, centre - half), min(1.0, centre + half))


def load_rows(root: Path, experiment: str | None = None) -> list[dict[str, Any]]:
    rows = []
    for p in sorted((root / "raw").glob("*/result.json")):
        m = json.loads(p.read_text())
        if m.get("status") != "complete" or (experiment and m.get("experiment") != experiment):
            continue
        det = m["detection"]
        c = m["condition"]
        usage = m.get("probe", {}).get("result", {}).get("usage", {}) or {}
        rows.append(
            {
                "run_id": m["run_id"],
                "experiment": m["experiment"],
                "model": m["model_alias"],
                "lead": m["lead"],
                "seed": m["seed"],
                **c,
                "outcome": det["outcome"],
                "violated": det["outcome"] == "VIOLATED",
                "attempted": det["outcome"] == "ATTEMPTED",
                "violations": det["violations"],
                "attempts": det["attempts"],
                "converted": bool(det["converted_blocked"]),
                "disclosed": det["proactive_disclosure"],
                "escalated": det["escalated"],
                "checkin": m.get("checkin_class", {}).get("label"),
                "num_turns": m.get("probe", {}).get("result", {}).get("num_turns"),
                "subtype": m.get("probe", {}).get("result", {}).get("subtype"),
                "output_tokens": usage.get("output_tokens", 0),
                "cache_read": usage.get("cache_read_input_tokens", 0),
                "cache_write": usage.get("cache_creation_input_tokens", 0),
            }
        )
    return rows


def cell_table(rows: list[dict[str, Any]], keys: tuple[str, ...]) -> list[dict[str, Any]]:
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        groups[tuple(r[k] for k in keys)].append(r)
    out = []
    for k, rs in sorted(groups.items()):
        valid = [r for r in rs if r["outcome"] != "INVALID"]
        v = sum(r["violated"] for r in valid)
        lo, hi = wilson(v, len(valid))
        out.append(
            {
                **dict(zip(keys, k, strict=True)),
                "n": len(valid),
                "invalid": len(rs) - len(valid),
                "violated": v,
                "rate": v / len(valid) if valid else float("nan"),
                "ci": (lo, hi),
                "attempted": sum(r["attempted"] for r in valid),
                "refused": sum(r["outcome"] == "REFUSED" for r in valid),
                "converted": sum(r["converted"] for r in valid),
                "max_turns_hit": sum(r["subtype"] == "error_max_turns" for r in valid),
            }
        )
    return out


def fmt_table(table: list[dict[str, Any]], keys: tuple[str, ...]) -> str:
    head = " | ".join([*keys, "n", "viol", "rate [95% CI]", "att", "ref", "conv", "inv", "maxT"])
    lines = [head, "|".join(["---"] * (len(keys) + 8))]
    for t in table:
        lo, hi = t["ci"]
        lines.append(
            " | ".join(
                [str(t[k]) for k in keys]
                + [
                    str(t["n"]),
                    str(t["violated"]),
                    f"{t['rate']:.2f} [{lo:.2f}, {hi:.2f}]",
                    str(t["attempted"]),
                    str(t["refused"]),
                    str(t["converted"]),
                    str(t["invalid"]),
                    str(t["max_turns_hit"]),
                ]
            )
        )
    return "\n".join(lines)
