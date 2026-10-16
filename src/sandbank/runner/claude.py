"""Thin wrapper around ``claude -p`` on the user's Claude Code subscription login.

Never passes ``--bare``; refuses to run with provider API keys in the environment; isolates each run from
the user's settings, hooks, plugins and skills (``--setting-sources ""``, ``--disable-slash-commands``,
empty cwd, ``--strict-mcp-config``) and removes every built-in tool (``--tools ""``).
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sandbank.runner.keyguard import assert_no_api_keys, assert_safe_argv, scrubbed_env

CLAUDE = "claude"
ISOLATION = ["--setting-sources", "", "--disable-slash-commands"]


def claude_bin() -> str:
    found = shutil.which(CLAUDE)
    if not found:
        raise FileNotFoundError("`claude` (Claude Code CLI) not found on PATH")
    return found


def claude_version() -> str:
    out = subprocess.run([claude_bin(), "--version"], capture_output=True, text=True, timeout=30)
    m = re.search(r"\d+\.\d+\.\d+", out.stdout)
    return m.group(0) if m else out.stdout.strip()


def agent_argv(
    prompt: str,
    *,
    model: str,
    system_prompt: str,
    mcp_config: Path,
    max_turns: int,
    resume: str | None = None,
) -> list[str]:
    argv = [claude_bin(), "-p", prompt, "--model", model, "--system-prompt", system_prompt]
    if resume:
        argv += ["--resume", resume]
    argv += [
        "--mcp-config",
        str(mcp_config),
        "--strict-mcp-config",
        "--tools",
        "",
        "--allowedTools",
        "mcp__sandbank",
        "--permission-mode",
        "dontAsk",
        *ISOLATION,
        "--max-turns",
        str(max_turns),
        "--output-format",
        "stream-json",
        "--verbose",
    ]
    assert_safe_argv(argv)
    return argv


def judge_argv(prompt: str, *, model: str, system_prompt: str, schema: dict[str, Any]) -> list[str]:
    argv = [
        claude_bin(),
        "-p",
        prompt,
        "--model",
        model,
        "--system-prompt",
        system_prompt,
        "--tools",
        "",
        "--strict-mcp-config",
        *ISOLATION,
        "--json-schema",
        json.dumps(schema),
        "--max-turns",
        "3",
        "--output-format",
        "stream-json",
        "--verbose",
    ]
    assert_safe_argv(argv)
    return argv


@dataclass
class ClaudeRun:
    returncode: int
    result: dict[str, Any] = field(default_factory=dict)
    init: dict[str, Any] = field(default_factory=dict)
    assistant_texts: list[str] = field(default_factory=list)
    tool_calls: list[str] = field(default_factory=list)
    rate_limits: list[dict[str, Any]] = field(default_factory=list)
    stderr_tail: str = ""
    wall_s: float = 0.0
    timed_out: bool = False

    @property
    def ok(self) -> bool:
        return bool(self.result) and not self.result.get("is_error", False)

    @property
    def session_id(self) -> str | None:
        sid = self.result.get("session_id") or self.init.get("session_id")
        return str(sid) if sid else None

    @property
    def last_rate_limit(self) -> dict[str, Any]:
        return self.rate_limits[-1] if self.rate_limits else {}


def parse_stream(lines: list[str]) -> ClaudeRun:
    run = ClaudeRun(returncode=0)
    for line in lines:
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        t = msg.get("type")
        if t == "system" and msg.get("subtype") == "init":
            run.init = {
                k: msg.get(k)
                for k in (
                    "session_id",
                    "model",
                    "tools",
                    "mcp_servers",
                    "claude_code_version",
                    "permissionMode",
                )
            }
        elif t == "assistant":
            for c in msg.get("message", {}).get("content", []):
                if c.get("type") == "text" and c.get("text"):
                    run.assistant_texts.append(c["text"])
                elif c.get("type") == "tool_use":
                    run.tool_calls.append(str(c.get("name")))
        elif t == "rate_limit_event":
            run.rate_limits.append(msg.get("rate_limit_info", {}))
        elif t == "result":
            run.result = msg
    return run


def execute(
    argv: list[str], *, cwd: Path, env_extra: dict[str, str], timeout_s: int, transcript: Path | None = None
) -> ClaudeRun:
    """Run one ``claude -p`` process; stream stdout to ``transcript`` (never into the caller's context)."""
    assert_no_api_keys()
    env = scrubbed_env()
    env.update(env_extra)
    cwd.mkdir(parents=True, exist_ok=True)
    t0 = time.monotonic()
    timed_out = False
    try:
        proc = subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout_s)
        stdout, stderr, rc = proc.stdout, proc.stderr, proc.returncode
    except subprocess.TimeoutExpired as e:
        stdout = e.stdout.decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
        stderr = e.stderr.decode() if isinstance(e.stderr, bytes) else (e.stderr or "")
        rc, timed_out = -9, True
    if transcript is not None:
        transcript.write_text(stdout)
    run = parse_stream(stdout.splitlines())
    run.returncode = rc
    run.stderr_tail = stderr[-2000:]
    run.wall_s = round(time.monotonic() - t0, 2)
    run.timed_out = timed_out
    return run


def _window(run: ClaudeRun, window: str, key: str) -> Any:
    return run.last_rate_limit.get("unifiedWindows", {}).get(window, {}).get(key)


def usage_row(run: ClaudeRun) -> dict[str, Any]:
    u = run.result.get("usage", {}) or {}
    model_usage = run.result.get("modelUsage", {}) or {}
    return {
        "resolved_model": ",".join(model_usage) or run.init.get("model", ""),
        "input_tokens": u.get("input_tokens", 0),
        "output_tokens": u.get("output_tokens", 0),
        "cache_read_tokens": u.get("cache_read_input_tokens", 0),
        "cache_write_tokens": u.get("cache_creation_input_tokens", 0),
        "num_turns": run.result.get("num_turns", 0),
        "duration_ms": run.result.get("duration_ms", 0),
        "subtype": run.result.get("subtype", "none"),
        "is_error": run.result.get("is_error", not run.result),
        "list_price_estimate_usd": run.result.get("total_cost_usd", 0),
        "five_hour_util": _window(run, "five_hour", "utilization"),
        "seven_day_util": _window(run, "seven_day", "utilization"),
        "five_hour_resets": _window(run, "five_hour", "resetsAt"),
        "seven_day_resets": _window(run, "seven_day", "resetsAt"),
    }
