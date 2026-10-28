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
BACKENDS = ("api", "claude-code")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="sandbank", description=DISCLAIMER)
    p.add_argument("--version", action="version", version=f"sandbank {__version__}")
    sub = p.add_subparsers(dest="command", required=True)
    demo = sub.add_parser("demo", help="run one live probe (or the scripted stub with --stub)")
    demo.add_argument("--stub", action="store_true", help="no model calls: scripted agents only")
    demo.add_argument("--results", type=Path, default=None)
    demo.add_argument("--model", default="haiku")
    demo.add_argument("--lead", default="B1", choices=list(BLOCKED_TYPES))
    demo.add_argument("--pressure", default="P3", choices=["P0", "P1", "P2", "P3", "P4", "P5"])
    demo.add_argument("--hardness", default="H1", choices=["H0", "H1", "H2"])
    demo.add_argument("--seed", type=int, default=1)
    demo.add_argument("--backend", choices=BACKENDS, default="api")
    run = sub.add_parser("run", help="run an experiment grid")
    run.add_argument("--backend", choices=BACKENDS, default="api")
    run.add_argument(
        "--budget-usd", type=float, default=None, help="cumulative spend cap (results/spend.json)"
    )
    run.add_argument("--config", type=Path, required=True)
    run.add_argument("--results", type=Path, default=Path("results"))
    run.add_argument("--batch-size", type=int, default=20)
    run.add_argument("--parallel", type=int, default=4, help="API backend: probes in flight")
    run.add_argument("--max-runs", type=int, default=None)
    run.add_argument("--max-util", type=float, default=0.95, help="pause when a usage window reaches this")
    run.add_argument("--stub", choices=["compliant", "violating", "idle"], default=None)
    judge = sub.add_parser("judge", help="label V7 / deception / eval-awareness cases in batches")
    judge.add_argument("--results", type=Path, default=Path("results"))
    judge.add_argument("--model", default="haiku")
    judge.add_argument("--backend", choices=BACKENDS, default="api")
    pl = sub.add_parser("plan", help="N plan from measured usage")
    pl.add_argument("--results", type=Path, default=Path("results"))
    pl.add_argument("--configs", type=Path, default=Path("configs"))
    pl.add_argument("--weekly-budget", type=float, default=0.8, help="claude-code backend only")
    pl.add_argument("--budget-usd", type=float, default=None, help="API backend: dollars for A–G")
    sm = sub.add_parser("summary", help="per-cell violation table for one experiment")
    sm.add_argument("--results", type=Path, default=Path("results"))
    sm.add_argument("--experiment", default=None)
    sm.add_argument("--by", default="model,pressure,frame")
    sp = sub.add_parser("spotcheck", help="export runs for hand-labelling")
    sp.add_argument("--results", type=Path, default=Path("results"))
    sp.add_argument("--experiment", default=None)
    sp.add_argument("--n", type=int, default=60)
    sp.add_argument(
        "--include", action="append", default=[], metavar="ROOT:K", help="also sample K runs from ROOT"
    )
    sp.add_argument("--score", action="store_true", help="score the labelled cases.csv against key.csv")
    for name in ("validate", "analyze", "paper"):
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
    if args.backend == "api":
        from sandbank.runner.api import make_client, sdk_version
        from sandbank.runner.run import run_one_api
        from sandbank.runner.spend import Ledger

        print(f"running {spec.run_id} through the Anthropic API (one probe + one check-in)...")
        meta = run_one_api(spec, root, make_client(), Ledger(root), sdk_version())
    else:
        assert_no_api_keys()
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
                "cost_usd": meta.get("cost_usd"),
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
    """Environment checks: API key and SDK (API backend), Claude Code (optional), stub pipeline."""
    import contextlib
    import io
    import shutil

    from sandbank.runner.api import MissingKeyError, load_credentials, sdk_version

    checks: list[tuple[str, bool, str]] = []
    try:
        load_credentials()
        checks.append(("API key (env or .env; not shown)", True, "found"))
    except MissingKeyError as e:
        checks.append(("API key (env or .env; not shown)", False, str(e)))
    checks.append(("anthropic SDK", True, sdk_version()))
    path = shutil.which("claude")
    checks.append(("claude on PATH (claude-code backend only; optional)", True, path or "not found"))
    with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
        ok = demo_stub(Path(tmp)) == 0
    checks.append(("stub pipeline (env + detector)", ok, "PASS" if ok else "FAIL"))
    for name, good, info in checks:
        print(f"[{'ok' if good else 'FAIL'}] {name}: {info}")
    return 0 if all(g for _, g, _ in checks) else 1


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if getattr(args, "backend", "api") == "claude-code":
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
    if args.command == "plan":
        from sandbank.analysis.plan import budget_plan, plan

        if args.budget_usd is not None:
            print(budget_plan(args.configs, args.results / "usage.csv", args.budget_usd))
        else:
            print(plan(args.configs, args.results / "usage.csv", args.weekly_budget))
        return 0
    if args.command == "summary":
        from sandbank.analysis.summary import cell_table, fmt_table, load_rows

        keys = tuple(args.by.split(","))
        print(fmt_table(cell_table(load_rows(args.results, args.experiment), keys), keys))
        return 0
    if args.command == "spotcheck":
        from sandbank.judge.spotcheck import export, score

        if args.score:
            print(score(args.results))
            return 0
        inc = [(Path(x.rsplit(":", 1)[0]), int(x.rsplit(":", 1)[1])) for x in args.include]
        print(export(args.results, args.n, args.experiment, include=inc))
        return 0
    if args.command == "validate":
        return validate()
    if args.command == "judge":
        from sandbank.judge.batch import api_labeler, claude_labeler, judge_all

        if args.backend == "api":
            from sandbank.runner.api import make_client
            from sandbank.runner.spend import Ledger

            labeler = api_labeler(args.model, make_client(), Ledger(args.results))
        else:
            labeler = claude_labeler(args.model, args.results)
        print(judge_all(args.results, labeler))
        return 0
    if args.command == "run":
        if args.backend == "api" and not args.stub:
            from sandbank.runner.run import run_config_api

            print(
                run_config_api(
                    args.config,
                    args.results,
                    parallel=args.parallel,
                    max_runs=args.max_runs,
                    budget_usd=args.budget_usd,
                )
            )
            return 0
        from sandbank.runner.run import run_config

        counts = run_config(
            args.config,
            args.results,
            batch_size=args.batch_size,
            parallel=1,
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
