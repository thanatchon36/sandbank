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
    for name in COMMANDS[1:]:
        sub.add_parser(name)
    return p


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
    print(f"sandbank {args.command}: not implemented yet", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
