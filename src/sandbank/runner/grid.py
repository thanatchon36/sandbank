"""Experiment grids (``configs/*.yaml``) → ordered run specs."""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from sandbank.env.conditions import Condition

FACTORS = ("pressure", "compliance", "oversight", "hardness", "mitigation", "frame")
DEFAULTS: dict[str, list[str]] = {
    "pressure": ["P1"],
    "compliance": ["C-"],
    "oversight": ["O0"],
    "hardness": ["H1"],
    "mitigation": ["none"],
    "frame": ["sales"],
}


@dataclass(frozen=True)
class RunSpec:
    experiment: str
    model: str
    condition: Condition
    lead: str  # B1–B6 for level 1; "EP" for level-2 episodes
    seed: int
    level: int
    max_turns: int
    tags: dict[str, Any] = field(default_factory=dict, hash=False, compare=False)

    @property
    def run_id(self) -> str:
        return f"{self.experiment}-{self.model}-{self.condition.code}-{self.lead}-s{self.seed:04d}"


def load_config(path: Path) -> dict[str, Any]:
    cfg: dict[str, Any] = yaml.safe_load(path.read_text())
    return cfg


def expand(cfg: dict[str, Any]) -> list[RunSpec]:
    """Grouped by (model, condition) so identical system prompts run back-to-back (warm cache)."""
    exp = str(cfg["experiment"])
    level = int(cfg.get("level", 1))
    max_turns = int(cfg.get("max_turns", 12 if level == 1 else 40))
    models: list[str] = list(cfg.get("models", ["haiku"]))
    n_cfg = cfg.get("n", 1)
    leads: list[str] = list(cfg.get("leads", ["B1", "B2", "B3", "B4", "B5", "B6"])) if level == 1 else ["EP"]
    seed_base = int(cfg.get("seed_base", 1000))
    grid = {f: list(cfg.get("grid", {}).get(f, DEFAULTS[f])) for f in FACTORS}
    cells = cfg.get("cells")  # optional explicit list of factor dicts (overrides the product)
    conds = (
        [Condition(**{**{f: DEFAULTS[f][0] for f in FACTORS}, **c}) for c in cells]
        if cells
        else [
            Condition(**dict(zip(FACTORS, combo, strict=True))) for combo in itertools.product(*grid.values())
        ]
    )
    specs: list[RunSpec] = []
    for model in models:
        n = int(n_cfg[model]) if isinstance(n_cfg, dict) else int(n_cfg)
        for cond in conds:
            for lead in leads:
                for i in range(n):
                    specs.append(RunSpec(exp, model, cond, lead, seed_base + i, level, max_turns))
    return specs
