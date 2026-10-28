"""Run experiment grids, resumable. Backends: ``api`` (default; Anthropic Messages API, budgeted, parallel)
and ``claude-code`` (experimental; one ``claude -p`` process per probe on a subscription login)."""

from __future__ import annotations

import csv
import datetime as dt
import json
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from functools import partial
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
from sandbank.runner.spend import BudgetExceeded, Ledger
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
    "five_hour_resets",
    "seven_day_resets",
    "timestamp",
]


_LOCK = threading.Lock()


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
    p = (root / "mcp.generated.json").resolve()
    p.write_text(json.dumps(cfg, indent=2))
    return p


def scenario_for(spec: RunSpec) -> Scenario:
    if spec.level == 2:
        return build_episode(spec.condition, spec.seed, spec.run_id)
    return build_probe(spec.condition, spec.lead, spec.seed, spec.run_id)


def append_usage(root: Path, run_id: str, kind: str, model: str, run: ClaudeRun) -> None:
    _append_usage_row(root, {"run_id": run_id, "kind": kind, "model": model, **usage_row(run)})


def _append_usage_row(root: Path, row: dict[str, Any]) -> None:
    p = root / "usage.csv"
    with _LOCK:
        new = not p.exists()
        with p.open("a", newline="") as f:
            w = csv.DictWriter(f, fieldnames=USAGE_FIELDS, extrasaction="ignore")
            if new:
                w.writeheader()
            w.writerow({**row, "timestamp": now_iso()})


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
    if probe.get("classifier_refusal") and meta["detection"]["outcome"] == "INVALID":
        # declined by the API's safety classifier before acting: reported as a REFUSED sub-count
        meta["detection"]["outcome"] = "REFUSED"
    meta["status"] = "complete"
    meta["completed_at"] = now_iso()
    return meta


class HarnessError(Exception):
    """`claude -p` produced no result (bad flags, missing config, crash): never recorded as a probe."""


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
        if not probe.result and not probe.timed_out and not is_limit(probe):
            raise HarnessError(f"{spec.run_id}: rc={probe.returncode} {probe.stderr_tail[-300:]}")
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
    if cfg.get("kind") == "comprehension":
        return run_comprehension_config(cfg, root, sleep=sleep)
    specs = expand(cfg)
    root.mkdir(parents=True, exist_ok=True)
    mcp_cfg = write_mcp_config(root)
    cc = "stub" if stub else claude_version()
    counts = {"complete": 0, "skipped": 0, "executed": 0}
    executed = 0
    harness_errors = 0
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
                    harness_errors = 0
                    break
                except HarnessError as he:
                    harness_errors += 1
                    log(f"harness error ({harness_errors}/3): {he}")
                    if harness_errors >= 3:
                        write_progress(root, {"config": str(config), "state": "aborted", "error": str(he)})
                        raise
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


def write_manifest(root: Path, backend: str = "claude-code") -> None:
    m: dict[str, Any] = {"sandbank_version": __version__, "git_commit": git_commit(), "backend": backend}
    if backend == "api":
        from sandbank.runner.api import MAX_TOKENS, sdk_version
        from sandbank.runner.pricing import ALIASES, EFFORT, PRICES, PRICES_AS_OF

        m |= {
            "anthropic_sdk_version": sdk_version(),
            "models": ALIASES,
            "effort": EFFORT,
            "max_tokens_per_call": MAX_TOKENS,
            "prices_usd_per_mtok": {k: v.__dict__ for k, v in PRICES.items()},
            "prices_as_of": PRICES_AS_OF,
        }
    else:
        m["claude_code_version"] = claude_version()
    (root / "manifest.json").write_text(json.dumps(m, indent=1))


def run_comprehension_config(
    cfg: dict[str, Any], root: Path, *, sleep: Callable[[float], None] = time.sleep
) -> dict[str, int]:
    from sandbank.scenarios.comprehension import run_comprehension

    root.mkdir(parents=True, exist_ok=True)
    for model in cfg.get("models", ["haiku"]):
        while True:
            try:
                log(f"comprehension {model}: {run_comprehension(root, str(model))}")
                break
            except TimeoutError as e:
                until = float(str(e).rsplit(" ", 1)[-1]) + 60
                log(f"pause: comprehension usage limit; sleeping until {until}")
                sleep(max(0.0, until - time.time()))
    return {"complete": 1, "skipped": 0, "executed": 1}


# --- API backend --------------------------------------------------------------------------------------

# Conservative per-run estimates (USD) used by the budget guard until a model has measured runs.
DEFAULT_RUN_ESTIMATE = {"haiku": 0.02, "sonnet": 0.30, "opus": 0.60}


class RunEstimator:
    """Running mean cost per completed run and model (probe + check-in), seeded with a default."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.sums: dict[str, tuple[float, int]] = {}

    def add(self, model: str, usd: float) -> None:
        with self.lock:
            s, n = self.sums.get(model, (0.0, 0))
            self.sums[model] = (s + usd, n + 1)

    def estimate(self, model: str) -> float:
        s, n = self.sums.get(model, (0.0, 0))
        mean = s / n if n else DEFAULT_RUN_ESTIMATE.get(model, 0.6)
        return 2 * mean  # headroom: a single run can cost well above the mean


def _api_usage_row(run_id: str, kind: str, model: str, ar: Any) -> dict[str, Any]:
    u = ar.usage()
    return {
        "run_id": run_id,
        "kind": kind,
        "model": model,
        "resolved_model": ",".join(sorted({c.model for c in ar.calls})),
        "input_tokens": u["input_tokens"],
        "output_tokens": u["output_tokens"],
        "cache_read_tokens": u["cache_read_input_tokens"],
        "cache_write_tokens": u["cache_creation_input_tokens"],
        "num_turns": ar.turns,
        "duration_ms": int(sum(c.wall_s for c in ar.calls) * 1000),
        "subtype": ar.subtype,
        "is_error": ar.error is not None,
        "list_price_estimate_usd": round(ar.cost_usd, 6),
    }


def run_one_api(spec: RunSpec, root: Path, client: Any, ledger: Ledger, sdk: str) -> dict[str, Any]:
    """One probe + Compliance check-in through the Messages API; resumable at the run level."""
    from sandbank.mcp_server import build_server
    from sandbank.runner.api import add_user_text, call_mcp_tool, mcp_tools, run_agent
    from sandbank.runner.pricing import EFFORT, model_id

    d = run_dir(root, spec.run_id)
    rpath = d / "result.json"
    if rpath.exists() and json.loads(rpath.read_text()).get("status") == "complete":
        return dict(json.loads(rpath.read_text()))
    sc = scenario_for(spec)
    prepare_run(root, sc)  # a run interrupted mid-way restarts from scratch
    mid = model_id(spec.model)
    meta: dict[str, Any] = {
        "run_id": spec.run_id,
        "experiment": spec.experiment,
        "model_alias": spec.model,
        "model_id": mid,
        "effort": EFFORT[mid],
        "backend": "api",
        "condition": spec.condition.to_dict(),
        "condition_code": spec.condition.code,
        "lead": spec.lead,
        "seed": spec.seed,
        "level": spec.level,
        "max_turns": spec.max_turns,
        "anthropic_sdk_version": sdk,
        "sandbank_version": __version__,
        "git_commit": git_commit(),
        "started_at": now_iso(),
        "stub": None,
    }
    app = build_server(d / "state.json", d / "events.jsonl")
    tools = mcp_tools(app)

    def charge(call: Any) -> None:
        ledger.add(call.cost_usd, experiment=spec.experiment, model=spec.model, kind="agent")

    for attempt in range(2):  # a max_tokens cut-off is a harness error: restart the probe once
        if attempt:
            prepare_run(root, sc)
            app = build_server(d / "state.json", d / "events.jsonl")
        messages: list[dict[str, Any]] = [{"role": "user", "content": sc.brief}]
        probe = run_agent(
            client,
            model=spec.model,
            system=sc.system_prompt,
            tools=tools,
            messages=messages,
            dispatch=partial(call_mcp_tool, app),
            max_turns=spec.max_turns,
            on_call=charge,
        )
        if probe.error != "max_tokens":
            break
        meta["max_tokens_restarts"] = attempt + 1
        meta["discarded_cost_usd"] = round(meta.get("discarded_cost_usd", 0.0) + probe.cost_usd, 6)
    _append_usage_row(root, _api_usage_row(spec.run_id, "probe", spec.model, probe))
    meta["probe"] = probe.summary()
    meta["assistant_texts"] = probe.assistant_texts
    meta["resolved_model"] = ",".join(sorted({c.model for c in probe.calls}))
    checkin_text: str | None = None
    if probe.error is None and not probe.classifier_refusal:
        set_phase(root, spec.run_id, "checkin")
        n_before = len(messages)
        add_user_text(messages, CHECKIN_PROMPT)
        ck = run_agent(
            client,
            model=spec.model,
            system=sc.system_prompt,
            tools=tools,
            messages=messages,
            dispatch=partial(call_mcp_tool, app),
            max_turns=CHECKIN_MAX_TURNS,
            on_call=charge,
        )
        _append_usage_row(root, _api_usage_row(spec.run_id, "checkin", spec.model, ck))
        meta["checkin"] = ck.summary()
        meta["checkin_texts"] = ck.assistant_texts
        checkin_text = ck.final_text
        meta["checkin_messages_from"] = n_before
    (d / "transcript.json").write_text(
        json.dumps({"system": sc.system_prompt, "messages": messages}, indent=1)
    )
    meta["cost_usd"] = round(
        meta.get("discarded_cost_usd", 0.0)
        + sum(c["cost_usd"] for k in ("probe", "checkin") for c in meta.get(k, {}).get("calls", [])),
        6,
    )
    meta = finalize(root, spec, meta, checkin_text)
    rpath.write_text(json.dumps(meta, indent=1))
    return meta


def run_config_api(
    config: Path,
    root: Path,
    *,
    parallel: int = 4,
    max_runs: int | None = None,
    budget_usd: float | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, int]:
    import anthropic

    from sandbank.runner.api import make_client, sdk_version

    cfg = load_config(config)
    root.mkdir(parents=True, exist_ok=True)
    client = make_client()
    ledger = Ledger(root)
    write_manifest(root, "api")
    if cfg.get("kind") == "comprehension":
        from sandbank.scenarios.comprehension import run_comprehension_api

        for model in cfg.get("models", ["haiku"]):
            ledger.check(budget_usd, 0.05)
            log(f"comprehension {model}: {run_comprehension_api(root, str(model), client, ledger)}")
        return {"complete": 1, "skipped": 0, "executed": 1}
    specs = expand(cfg)
    todo = [s for s in specs if not meta_done(root, s)]
    if max_runs is not None:
        todo = todo[:max_runs]
    counts = {
        "complete": len(specs) - len(todo),
        "skipped": len(specs) - len(todo),
        "executed": 0,
        "failed": 0,
    }
    est = RunEstimator()
    sdk = sdk_version()
    stop = threading.Event()

    def progress(state: str, extra: dict[str, Any] | None = None) -> None:
        with _LOCK:
            write_progress(
                root,
                {
                    "config": str(config),
                    "backend": "api",
                    "total": len(specs),
                    "done": counts["complete"],
                    "failed": counts["failed"],
                    "state": state,
                    "spend_usd": round(ledger.total, 4),
                    "budget_usd": budget_usd,
                    **(extra or {}),
                },
            )

    def work(spec: RunSpec) -> None:
        if stop.is_set() or (root / "STOP").exists():
            stop.set()
            return
        for attempt in range(4):
            try:
                ledger.check(budget_usd, est.estimate(spec.model))
                meta = run_one_api(spec, root, client, ledger, sdk)
                est.add(spec.model, float(meta.get("cost_usd", 0.0)))
                with _LOCK:
                    counts["complete"] += 1
                    counts["executed"] += 1
                log(f"{spec.run_id}: {meta['detection']['outcome']} (${meta.get('cost_usd', 0):.4f})")
                progress("running", {"current": spec.run_id})
                return
            except BudgetExceeded as e:
                log(f"stop: {e}")
                stop.set()
                return
            except (
                anthropic.RateLimitError,
                anthropic.InternalServerError,
                anthropic.APIConnectionError,
            ) as e:
                wait = 60.0 * (attempt + 1)
                log(f"{spec.run_id}: {type(e).__name__} after SDK retries; waiting {wait:.0f}s")
                with (root / "limits.jsonl").open("a") as f:
                    f.write(
                        json.dumps({"at": now_iso(), "run": spec.run_id, "error": type(e).__name__}) + "\n"
                    )
                sleep(wait)
            except anthropic.APIStatusError as e:
                log(f"{spec.run_id}: API error {e.status_code}: {str(e.message)[:300]}")
                break
        with _LOCK:
            counts["failed"] += 1
        progress("running", {"last_failure": spec.run_id})
        if counts["failed"] >= 5 and counts["executed"] == 0:
            stop.set()

    progress("running")
    with ThreadPoolExecutor(max_workers=max(1, parallel)) as pool:
        list(pool.map(work, todo))
    state = "stopped" if stop.is_set() else "finished"
    progress(state)
    log(f"{state}: {counts}; spend ${ledger.total:.4f}")
    return counts
