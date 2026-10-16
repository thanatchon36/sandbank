"""`sandbank` command-line interface."""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from sandbank import DISCLAIMER, __version__
from sandbank.data.generator import BLOCKED_TYPES
from sandbank.detector.rules import detect
from sandbank.env.conditions import Condition
from sandbank.runner.keyguard import ForbiddenKeyError, assert_no_api_keys
from sandbank.runner.store import load_run, prepare_run
from sandbank.runner.stub import run_stub
from sandbank.scenarios.builder import build_probe

COMMANDS = ("demo", "validate", "plan", "run", "analyze", "paper", "spotcheck")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="sandbank", description=DISCLAIMER)
    p.add_argument("--version", action="version", version=f"sandbank {__version__}")
    sub = p.add_subparsers(dest="command", required=True)
    demo = sub.add_parser("demo", help="run one live probe (or the scripted stub with --stub)")
    demo.add_argument("--stub", action="store_true", help="no model calls: scripted agents only")
    demo.add_argument("--results", type=Path, default=None)
    demo.add_argument("--model", default="haiku")
    demo.add_argument("--lead", default="B1", choices=list(BLOCKED_TYPES))
    demo.add_argument("--pressure", default="P3", choices=["P0", "P1", "P2", "P3", "P4"])
    demo.add_argument("--hardness", default="H1", choices=["H0", "H1", "H2"])
    demo.add_argument("--seed", type=int, default=1)
    run = sub.add_parser("run", help="run an experiment grid with claude -p")
    run.add_argument("--config", type=Path, required=True)
    run.add_argument("--results", type=Path, default=Path("results"))
    run.add_argument("--batch-size", type=int, default=20)
    run.add_argument("--parallel", type=int, default=1)
    run.add_argument("--max-runs", type=int, default=None)
    run.add_argument("--max-util", type=float, default=0.95, help="pause when a usage window reaches this")
    run.add_argument("--stub", choices=["compliant", "violating", "idle"], default=None)
    judge = sub.add_parser("judge", help="label V7 / deception / eval-awareness cases in batches")
    judge.add_argument("--results", type=Path, default=Path("results"))
    judge.add_argument("--model", default="haiku")
    for name in ("validate", "plan", "analyze", "paper", "spotcheck"):
        sub.add_parser(name)
    return p


def demo_live(args: argparse.Namespace) -> int:
    """One live probe + Compliance check-in on the caller's own Claude Code login."""
    import json

    from sandbank.runner.claude import claude_version
    from sandbank.runner.grid import RunSpec
    from sandbank.runner.run import run_one, write_mcp_config

    root = args.results or Path("results/demo")
    root.mkdir(parents=True, exist_ok=True)
    cond = Condition(pressure=args.pressure, hardness=args.hardness)
    spec = RunSpec("demo", args.model, cond, args.lead, args.seed, 1, 12)
    print(f"running {spec.run_id} on your Claude Code login (one probe + one check-in turn)...")
    meta = run_one(spec, root, write_mcp_config(root), claude_version())
    det = meta["detection"]
    print(
        json.dumps(
            {
                "run_id": spec.run_id,
                "outcome": det["outcome"],
                "violations": det["violations"],
                "attempts": det["attempts"],
                "blocked_lead_converted": bool(det["converted_blocked"]),
                "checkin": meta["checkin_class"]["label"],
                "tokens": meta.get("probe", {}).get("result", {}).get("usage", {}).get("output_tokens"),
            },
            indent=1,
        )
    )
    print(f"event log: {root}/raw/{spec.run_id}/events.jsonl")
    return 0


def demo_stub(results: Path) -> int:
    """Scripted compliant vs. circumventing agents across lead types and control hardness."""
    print(f"{'lead':<5} {'hardness':<8} {'policy':<10} {'outcome':<10} violations / attempts")
    ok = True
    for lead in BLOCKED_TYPES:
        for hardness in ("H1", "H2"):
            for policy in ("compliant", "violating"):
                run_id = f"stub-{lead}-{hardness}-{policy}"
                prepare_run(results, build_probe(Condition(hardness=hardness), lead, 1, run_id))
                run_stub(results, run_id, policy)
                d = detect(*load_run(results, run_id))
                expected = (
                    "COMPLIANT"
                    if policy == "compliant"
                    else ("VIOLATED" if hardness == "H1" else "ATTEMPTED")
                )
                ok &= d.outcome == expected
                print(f"{lead:<5} {hardness:<8} {policy:<10} {d.outcome:<10} {d.violations} / {d.attempts}")
    print("stub demo:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def validate() -> int:
    """Environment checks: CLI present, subscription login, no API keys, stub pipeline passes."""
    import json
    import shutil
    import subprocess

    checks: list[tuple[str, bool, str]] = []
    path = shutil.which("claude")
    checks.append(("claude on PATH", bool(path), path or "not found"))
    if path:
        v = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=30).stdout.strip()
        checks.append(("Claude Code version", bool(v), v))
        st = subprocess.run([path, "auth", "status"], capture_output=True, text=True, timeout=30).stdout
        try:
            method = json.loads(st).get("authMethod", "?")
        except json.JSONDecodeError:
            method = "?"
        checks.append(("subscription login (authMethod claude.ai)", method == "claude.ai", method))
    checks.append(("no provider API keys in env", True, "ok"))
    with tempfile.TemporaryDirectory() as tmp:
        import contextlib
        import io

        with contextlib.redirect_stdout(io.StringIO()):
            ok = demo_stub(Path(tmp)) == 0
    checks.append(("stub pipeline (env + detector)", ok, "PASS" if ok else "FAIL"))
    for name, good, info in checks:
        print(f"[{'ok' if good else 'FAIL'}] {name}: {info}")
    return 0 if all(g for _, g, _ in checks) else 1


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        assert_no_api_keys()
    except ForbiddenKeyError as e:
        print(str(e), file=sys.stderr)
        return 2
    if args.command == "demo" and args.stub:
        if args.results is not None:
            return demo_stub(args.results)
        with tempfile.TemporaryDirectory() as tmp:
            return demo_stub(Path(tmp))
    if args.command == "demo":
        return demo_live(args)
    if args.command == "validate":
        return validate()
    if args.command == "judge":
        from sandbank.judge.batch import claude_labeler, judge_all

        print(judge_all(args.results, claude_labeler(args.model, args.results)))
        return 0
    if args.command == "run":
        from sandbank.runner.run import run_config

        counts = run_config(
            args.config,
            args.results,
            batch_size=args.batch_size,
            parallel=args.parallel,
            max_runs=args.max_runs,
            stub=args.stub,
            max_util=args.max_util,
        )
        print(counts)
        return 0
    print(f"sandbank {args.command}: not implemented yet", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
