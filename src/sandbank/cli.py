"""`sandbank` command-line interface."""

from __future__ import annotations

import argparse
import sys

from sandbank import DISCLAIMER, __version__
from sandbank.runner.keyguard import ForbiddenKeyError, assert_no_api_keys

COMMANDS = ("demo", "validate", "plan", "run", "analyze", "paper", "spotcheck")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="sandbank", description=DISCLAIMER)
    p.add_argument("--version", action="version", version=f"sandbank {__version__}")
    sub = p.add_subparsers(dest="command", required=True)
    for name in COMMANDS:
        sub.add_parser(name)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        assert_no_api_keys()
    except ForbiddenKeyError as e:
        print(str(e), file=sys.stderr)
        return 2
    print(f"sandbank {args.command}: not implemented yet", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
