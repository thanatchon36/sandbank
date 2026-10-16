"""Per-run directory layout under ``results/raw/<run_id>/``."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from sandbank.env.bank import load_state, read_events, run_dir, save_state
from sandbank.scenarios.builder import Scenario


def prepare_run(root: Path, sc: Scenario, overwrite: bool = True) -> Path:
    d = run_dir(root, sc.run_id)
    if d.exists() and overwrite:
        shutil.rmtree(d)
    d.mkdir(parents=True, exist_ok=True)
    save_state(d / "state.json", sc.state)
    (d / "scenario.json").write_text(
        json.dumps(
            {
                "run_id": sc.run_id,
                "system_prompt": sc.system_prompt,
                "brief": sc.brief,
                "initial_state": sc.state,
            },
            indent=1,
        )
    )
    (d / "events.jsonl").touch()
    return d


def load_run(root: Path, run_id: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    d = run_dir(root, run_id)
    return load_state(d / "state.json"), read_events(d / "events.jsonl")


def set_phase(root: Path, run_id: str, phase: str) -> None:
    p = run_dir(root, run_id) / "state.json"
    st = load_state(p)
    st["phase"] = phase
    save_state(p, st)
