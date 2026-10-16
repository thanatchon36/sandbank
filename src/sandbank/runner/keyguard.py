"""Refuse to run when any pay-per-token provider key is present.

SandBank runs every model call through `claude -p` on the user's Claude Code
subscription login. A provider API key in the environment could silently switch
Claude Code to metered billing, so the runner refuses to start instead.
"""

from __future__ import annotations

import os
from collections.abc import Mapping

FORBIDDEN_KEYS: tuple[str, ...] = ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY")
FORBIDDEN_FLAGS: tuple[str, ...] = ("--bare",)


class ForbiddenKeyError(RuntimeError):
    """Raised when a provider API key is set in the environment."""


def present_keys(env: Mapping[str, str] | None = None) -> list[str]:
    """Return the names of forbidden keys that are set (non-empty) in ``env``."""
    env = os.environ if env is None else env
    return [k for k in FORBIDDEN_KEYS if env.get(k)]


def assert_no_api_keys(env: Mapping[str, str] | None = None) -> None:
    """Raise :class:`ForbiddenKeyError` if any forbidden key is set."""
    found = present_keys(env)
    if found:
        raise ForbiddenKeyError(
            "sandbank refuses to start: "
            + ", ".join(found)
            + " is set. SandBank uses only your Claude Code subscription login via "
            "`claude -p`; unset the variable(s) and retry."
        )


def assert_safe_argv(argv: list[str]) -> None:
    """Raise if a `claude` command line contains a forbidden flag (e.g. ``--bare``)."""
    bad = [a for a in argv if a in FORBIDDEN_FLAGS or a.startswith("--bare=")]
    if bad:
        raise ForbiddenKeyError(f"forbidden claude flag(s): {', '.join(bad)}")


def scrubbed_env(env: Mapping[str, str] | None = None) -> dict[str, str]:
    """Copy of ``env`` guaranteed to contain no forbidden keys (defence in depth)."""
    env = os.environ if env is None else env
    return {k: v for k, v in env.items() if k not in FORBIDDEN_KEYS}
