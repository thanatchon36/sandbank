"""Run experiment grids: one ``claude -p`` process per probe, resumable, paced by plan usage windows."""

from __future__ import annotations

import csv
import datetime as dt
import json
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from sandbank import __version__
from sandbank.detector.checkin import classify_checkin
from sandbank.detector.rules import detect
from sandbank.env.bank import run_dir
from sandbank.runner.claude import ClaudeRun, agent_argv, claude_version, execute, usage_row
from sandbank.runner.grid import RunSpec, expand, load_config
from sandbank.runner.keyguard import assert_no_api_keys
from sandbank.runner.limits import OVERLOAD_WAIT_S, guard, is_limit, is_overload, reset_epoch
from sandbank.runner.store import load_run, prepare_run, set_phase
from sandbank.runner.stub import run_stub
from sandbank.scenarios.briefs import CHECKIN_PROMPT
from sandbank.scenarios.builder import Scenario, build_episode, build_probe

CHECKIN_MAX_TURNS = 3
USAGE_FIELDS = [
    "run_id",
    "kind",
    "model",
    "resolved_model",
    "input_tokens",
    "output_tokens",
    "cache_read_tokens",
    "cache_write_tokens",
    "num_turns",
    "duration_ms",
    "subtype",
    "is_error",
    "list_price_estimate_usd",
    "five_hour_util",
    "seven_day_util",
    "timestamp",
]


def now_iso() -> str:
    return dt.datetime.now(dt.UTC).isoformat(timespec="seconds")


def log(msg: str) -> None:
    print(f"[{dt.datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def git_commit() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=10
        )
        return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def write_mcp_config(root: Path) -> Path:
    cfg = {
        "mcpServers": {
            "sandbank": {
                "type": "stdio",
                "command": sys.executable,
                "args": ["-m", "sandbank.mcp_server"],
                "env": {"SANDBANK_RUN": "${SANDBANK_RUN}", "SANDBANK_RESULTS": str(root.resolve())},
            }
        }
    }
    p = root / "mcp.generated.json"
    p.write_text(json.dumps(cfg, indent=2))
    return p


def scenario_for(spec: RunSpec) -> Scenario:
    if spec.level == 2:
        return build_episode(spec.condition, spec.seed, spec.run_id)
    return build_probe(spec.condition, spec.lead, spec.seed, spec.run_id)


def append_usage(root: Path, run_id: str, kind: str, model: str, run: ClaudeRun) -> None:
    p = root / "usage.csv"
    new = not p.exists()
    with p.open("a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=USAGE_FIELDS)
        if new:
            w.writeheader()
        w.writerow({"run_id": run_id, "kind": kind, "model": model, **usage_row(run), "timestamp": now_iso()})


def _summary(run: ClaudeRun) -> dict[str, Any]:
    keep = (
        "subtype",
        "is_error",
        "result",
        "session_id",
        "num_turns",
        "usage",
        "modelUsage",
        "duration_ms",
        "stop_reason",
        "terminal_reason",
        "api_error_status",
        "permission_denials",
        "total_cost_usd",
    )
    return {
        "result": {k: run.result.get(k) for k in keep if k in run.result},
        "init": run.init,
        "returncode": run.returncode,
        "timed_out": run.timed_out,
        "wall_s": run.wall_s,
        "rate_limit": run.last_rate_limit,
        "n_tool_calls": len(run.tool_calls),
        "stderr_tail": run.stderr_tail[-500:],
    }


def finalize(root: Path, spec: RunSpec, meta: dict[str, Any], checkin_text: str | None) -> dict[str, Any]:
    state, events = load_run(root, spec.run_id)
    det = detect(state, events)
    meta["detection"] = det.to_dict()
    meta["checkin_class"] = classify_checkin(det, checkin_text)
    probe = meta.get("probe", {})
    if (
        probe
        and probe.get("result", {}).get("is_error")
        and probe["result"].get("subtype") != "error_max_turns"
    ):
        meta["detection"]["outcome"] = "INVALID"
    meta["status"] = "complete"
    meta["completed_at"] = now_iso()
    return meta


class Pause(Exception):
    def __init__(self, until: float, reason: str) -> None:
        super().__init__(reason)
        self.until, self.reason = until, reason


def run_one(
    spec: RunSpec,
    root: Path,
    mcp_cfg: Path,
    cc_version: str,
    *,
    timeout_s: int = 900,
    stub: str | None = None,
    max_util: float = 0.95,
) -> dict[str, Any]:
    d = run_dir(root, spec.run_id)
    rpath = d / "result.json"
    meta: dict[str, Any] = json.loads(rpath.read_text()) if rpath.exists() else {}
    if meta.get("status") == "complete":
        return meta
    env = {"SANDBANK_RUN": spec.run_id, "SANDBANK_RESULTS": str(root.resolve())}
    sc = scenario_for(spec)
    if meta.get("status") != "probe_done":
        prepare_run(root, sc)
        meta = {
            "run_id": spec.run_id,
            "experiment": spec.experiment,
            "model_alias": spec.model,
            "condition": spec.condition.to_dict(),
            "condition_code": spec.condition.code,
            "lead": spec.lead,
            "seed": spec.seed,
            "level": spec.level,
            "max_turns": spec.max_turns,
            "claude_code_version": cc_version,
            "sandbank_version": __version__,
            "git_commit": git_commit(),
            "started_at": now_iso(),
            "stub": stub,
        }
        if stub:
            run_stub(root, spec.run_id, stub)
            meta["probe"] = {}
            meta = finalize(root, spec, meta, None)
            rpath.write_text(json.dumps(meta, indent=1))
            return meta
        argv = agent_argv(
            sc.brief,
            model=spec.model,
            system_prompt=sc.system_prompt,
            mcp_config=mcp_cfg,
            max_turns=spec.max_turns,
        )
        probe = execute(argv, cwd=d / "cwd", env_extra=env, timeout_s=timeout_s, transcript=d / "probe.jsonl")
        append_usage(root, spec.run_id, "probe", spec.model, probe)
        if is_limit(probe):
            raise Pause(reset_epoch(probe) + 60, "usage limit reached during probe")
        if is_overload(probe):
            raise Pause(time.time() + OVERLOAD_WAIT_S, "API overloaded")
        meta["probe"] = _summary(probe)
        meta["assistant_texts"] = probe.assistant_texts
        meta["resolved_model"] = probe.init.get("model")
        meta["status"] = "probe_done"
        rpath.write_text(json.dumps(meta, indent=1))
        g = guard(probe, max_util)
        if g:
            # finish this run's check-in first only if the window is not exhausted
            log(f"utilization guard: {g[0]} ≥ {max_util}; will pause after this run")
    sid = meta.get("probe", {}).get("result", {}).get("session_id")
    checkin_text: str | None = None
    if sid and not stub:
        set_phase(root, spec.run_id, "checkin")
        argv = agent_argv(
            CHECKIN_PROMPT,
            model=spec.model,
            system_prompt=sc.system_prompt,
            mcp_config=mcp_cfg,
            max_turns=CHECKIN_MAX_TURNS,
            resume=str(sid),
        )
        ck = execute(argv, cwd=d / "cwd", env_extra=env, timeout_s=300, transcript=d / "checkin.jsonl")
        append_usage(root, spec.run_id, "checkin", spec.model, ck)
        if is_limit(ck):
            raise Pause(reset_epoch(ck) + 60, "usage limit reached during check-in")
        meta["checkin"] = _summary(ck)
        checkin_text = str(ck.result.get("result", "")) if ck.result else None
        meta["checkin_texts"] = ck.assistant_texts
        g = guard(ck, max_util)
        meta = finalize(root, spec, meta, checkin_text)
        rpath.write_text(json.dumps(meta, indent=1))
        if g:
            raise Pause(g[1] + 60, f"{g[0]} window at/above {max_util} utilization")
        return meta
    meta = finalize(root, spec, meta, checkin_text)
    rpath.write_text(json.dumps(meta, indent=1))
    return meta


def write_progress(root: Path, payload: dict[str, Any]) -> None:
    p = root / "progress.json"
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps({**payload, "updated": now_iso()}, indent=1))
    tmp.replace(p)


def run_config(
    config: Path,
    root: Path,
    *,
    batch_size: int = 20,
    parallel: int = 1,
    max_runs: int | None = None,
    stub: str | None = None,
    max_util: float = 0.95,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, int]:
    assert_no_api_keys()
    if parallel != 1:
        log("note: --parallel > 1 is not implemented in v1; running sequentially")
    cfg = load_config(config)
    specs = expand(cfg)
    root.mkdir(parents=True, exist_ok=True)
    mcp_cfg = write_mcp_config(root)
    cc = "stub" if stub else claude_version()
    counts = {"complete": 0, "skipped": 0, "executed": 0}
    executed = 0
    batches = [specs[i : i + batch_size] for i in range(0, len(specs), batch_size)]
    for bi, batch in enumerate(batches):
        for spec in batch:
            rpath = run_dir(root, spec.run_id) / "result.json"
            if rpath.exists() and json.loads(rpath.read_text()).get("status") == "complete":
                counts["skipped"] += 1
                continue
            if max_runs is not None and executed >= max_runs:
                return counts
            while True:
                write_progress(
                    root,
                    {
                        "config": str(config),
                        "total": len(specs),
                        "done": counts["complete"] + counts["skipped"],
                        "batch": f"{bi + 1}/{len(batches)}",
                        "current": spec.run_id,
                        "state": "running",
                    },
                )
                try:
                    run_one(spec, root, mcp_cfg, cc, stub=stub, max_util=max_util)
                    break
                except Pause as p:
                    wait = max(0.0, p.until - time.time())
                    until = dt.datetime.fromtimestamp(p.until).isoformat(timespec="minutes")
                    log(f"pause: {p.reason}; sleeping {wait / 60:.0f} min until {until}")
                    with (root / "limits.jsonl").open("a") as f:
                        f.write(json.dumps({"at": now_iso(), "reason": p.reason, "until": p.until}) + "\n")
                    write_progress(
                        root,
                        {
                            "config": str(config),
                            "total": len(specs),
                            "done": counts["complete"] + counts["skipped"],
                            "current": spec.run_id,
                            "state": "paused",
                            "paused_until": until,
                            "reason": p.reason,
                        },
                    )
                    if (root / "STOP").exists():
                        log("STOP file present; exiting")
                        return counts
                    sleep(wait)
                    if meta_done(root, spec):
                        break
            executed += 1
            counts["executed"] += 1
            counts["complete"] += 1
            done = json.loads((run_dir(root, spec.run_id) / "result.json").read_text())
            log(f"{spec.run_id}: {done.get('detection', {}).get('outcome', '?')}")
    write_progress(
        root, {"config": str(config), "total": len(specs), "done": len(specs), "state": "finished"}
    )
    return counts


def meta_done(root: Path, spec: RunSpec) -> bool:
    p = run_dir(root, spec.run_id) / "result.json"
    return p.exists() and json.loads(p.read_text()).get("status") == "complete"


def write_manifest(root: Path) -> None:
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "sandbank_version": __version__,
                "git_commit": git_commit(),
                "claude_code_version": claude_version(),
            },
            indent=1,
        )
    )
