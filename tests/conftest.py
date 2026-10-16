from pathlib import Path

import pytest

from sandbank.env.bank import Bank
from sandbank.env.conditions import Condition
from sandbank.scenarios.builder import build_probe


@pytest.fixture
def results(tmp_path: Path) -> Path:
    return tmp_path / "results"


def make_bank(lead: str = "B1", seed: int = 1, **cond: str) -> Bank:
    sc = build_probe(Condition(**cond), lead, seed, f"t-{lead}-{seed}")  # type: ignore[arg-type]
    return Bank(sc.state)
