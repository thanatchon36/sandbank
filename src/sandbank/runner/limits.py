"""Usage-limit handling: limits are a pause, never a purchase."""

from __future__ import annotations

import re
import time
from typing import Any

from sandbank.runner.claude import ClaudeRun

FALLBACK_WAIT_S = 30 * 60
OVERLOAD_WAIT_S = 120
_LIMIT_RE = re.compile(r"usage limit|limit reached|rate.?limit|hit your limit|resets? (at|in)?", re.I)


def is_limit(run: ClaudeRun) -> bool:
    if run.last_rate_limit.get("status") == "rejected":
        return True
    if not run.result.get("is_error") and run.result:
        return False
    text = " ".join([str(run.result.get("result", "")), run.stderr_tail, *run.assistant_texts[-1:]])
    return run.result.get("api_error_status") in (429,) or bool(_LIMIT_RE.search(text))


def is_overload(run: ClaudeRun) -> bool:
    return (
        run.result.get("api_error_status") in (500, 502, 503, 529) or "overloaded" in run.stderr_tail.lower()
    )


def reset_epoch(run: ClaudeRun, now: float | None = None) -> float:
    """Best estimate of when the binding window resets (epoch seconds)."""
    now = time.time() if now is None else now
    info: dict[str, Any] = run.last_rate_limit
    if info.get("resetsAt"):
        return float(info["resetsAt"])
    text = " ".join([str(run.result.get("result", "")), run.stderr_tail])
    m = re.search(r"\|(\d{10})\b", text)
    if m:
        return float(m.group(1))
    return now + FALLBACK_WAIT_S


def guard(run: ClaudeRun, max_util: float) -> tuple[str, float] | None:
    """If any window is at/above ``max_util``, return (window, resets_at) to pause until; else None."""
    windows = run.last_rate_limit.get("unifiedWindows", {}) or {}
    worst: tuple[str, float] | None = None
    for name, w in windows.items():
        util, resets = w.get("utilization"), w.get("resetsAt")
        if util is not None and resets and float(util) >= max_util:
            cand = (str(name), float(resets))
            if worst is None or cand[1] > worst[1]:
                worst = cand
    return worst
