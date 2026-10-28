"""Spend ledger (``results/spend.json``) and the budget guard. Thread-safe within one process."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any


class BudgetExceeded(RuntimeError):
    """Starting the next probe could cross the budget cap."""


class Ledger:
    """Accumulates list-price spend per experiment, model and kind; persisted after every call."""

    def __init__(self, root: Path) -> None:
        self.path = root / "spend.json"
        self.lock = threading.Lock()
        self.data: dict[str, Any] = (
            json.loads(self.path.read_text())
            if self.path.exists()
            else {"total_usd": 0.0, "calls": 0, "by_experiment": {}, "by_model": {}, "by_kind": {}}
        )

    @property
    def total(self) -> float:
        return float(self.data["total_usd"])

    def add(self, usd: float, *, experiment: str, model: str, kind: str) -> None:
        with self.lock:
            self.data["total_usd"] = round(self.total + usd, 6)
            self.data["calls"] = int(self.data["calls"]) + 1
            for key, val in (("by_experiment", experiment), ("by_model", model), ("by_kind", kind)):
                bucket = self.data[key]
                bucket[val] = round(float(bucket.get(val, 0.0)) + usd, 6)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.data, indent=1, sort_keys=True))
            tmp.replace(self.path)

    def check(self, cap: float | None, next_estimate: float) -> None:
        """Raise if spend so far plus the estimate for the next unit of work would exceed ``cap``."""
        if cap is not None and self.total + next_estimate > cap:
            raise BudgetExceeded(
                f"budget cap ${cap:.2f}: spent ${self.total:.4f}, next run estimated ${next_estimate:.4f}"
            )
