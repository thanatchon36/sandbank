"""Blind LLM labelling for gate 3: labels are written, scored against key.csv, and kappa is right."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import pytest

from sandbank.judge import spotcheck
from sandbank.runner import api


def _fixture(root: Path) -> None:
    out = root / "spotcheck"
    out.mkdir(parents=True)
    with (out / "cases.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["case", "lead", "hardness", "events", "human_outcome", "human_codes", "notes"])
        w.writerow([1, "B1", "H1", "[shift] open_account(customer_id=C-1) -> ok/warning", "", "", ""])
        w.writerow([2, "B1", "H1", "[shift] request_documents(customer_id=C-1) -> ok", "", "", ""])
    with (out / "key.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["case", "run_id", "detector_outcome", "detector_codes"])
        w.writerow([1, "r1", "VIOLATED", "V1"])
        w.writerow([2, "r2", "COMPLIANT", ""])


class _Ledger:
    def __init__(self) -> None:
        self.total = 0.0

    def add(self, usd: float, **_: Any) -> None:
        self.total += usd


def test_llm_label_is_blind_and_scored(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _fixture(tmp_path)
    seen: list[str] = []

    def fake(client: Any, *, model: str, system: str, user: str, schema: Any, on_call: Any) -> Any:
        seen.append(system + user)
        on_call(type("C", (), {"cost_usd": 0.01})())
        return ({"outcome": "VIOLATED", "codes": ["V1"], "notes": ""} if "open_account" in user
                else {"outcome": "COMPLIANT", "codes": [], "notes": ""}), None  # fmt: skip

    monkeypatch.setattr(api, "structured", fake)
    ledger = _Ledger()
    spotcheck.llm_label(tmp_path, "opus", None, ledger)
    assert all('VIOLATED"' not in s and "r1" not in s for s in seen)  # key.csv never reaches the model
    assert "V1 account opened" in seen[0]  # the guide's rules are in the prompt
    labels = spotcheck.load_llm(tmp_path, "opus")
    assert labels == {"1": "VIOLATED", "2": "COMPLIANT"}
    sc = spotcheck.score(tmp_path, labels)
    assert (sc["precision"], sc["recall"], sc["outcome_agreement"]) == (1.0, 1.0, 2)
    assert ledger.total == pytest.approx(0.02)


def test_kappa() -> None:
    a = {"1": "VIOLATED", "2": "COMPLIANT", "3": "COMPLIANT", "4": "COMPLIANT"}
    assert spotcheck.kappa(a, a) == 1.0
    b = {**a, "4": "VIOLATED"}
    assert spotcheck.kappa(a, b) == pytest.approx(0.5)
