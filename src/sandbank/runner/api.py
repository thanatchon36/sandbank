"""Anthropic Messages API backend: a manual tool loop over the in-process SandBank MCP server.

The agent's tools are the FastMCP server's own tools (``sandbank.mcp_server.build_server``), listed and
called in-process, so names, descriptions, schemas, argument validation and result text are the ones the
MCP server exposes. The server's ``events.jsonl`` stays the ground truth.

The API key comes from ``ANTHROPIC_API_KEY`` or, if unset, from ``.env`` in the working directory. It is
never printed or written anywhere else. Do not export it in the shell that runs Claude Code: Claude Code
would switch that session to metered API billing.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import anthropic
from mcp.server.fastmcp import FastMCP

from sandbank.runner.pricing import EFFORT, call_cost, model_id

MAX_TOKENS = 8000
KEY_VAR = "ANTHROPIC_API_KEY"
WORKSPACE_VAR = "ANTHROPIC_WORKSPACE_ID"


class MissingKeyError(RuntimeError):
    """No API key in the environment or in ``.env``."""


def _dotenv(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip().strip("'\"")
    return out


def load_credentials(cwd: Path | None = None) -> tuple[str, str | None]:
    """(api_key, workspace_id or None). Environment first, then ``.env``."""
    env = _dotenv((cwd or Path.cwd()) / ".env")
    key = os.environ.get(KEY_VAR) or env.get(KEY_VAR)
    if not key:
        raise MissingKeyError(
            f"sandbank's API backend needs {KEY_VAR}: put `{KEY_VAR}=sk-ant-...` in a git-ignored .env "
            "file at the repo root (do not export it in the shell that runs Claude Code)."
        )
    return key, os.environ.get(WORKSPACE_VAR) or env.get(WORKSPACE_VAR) or None


def make_client(cwd: Path | None = None) -> anthropic.Anthropic:
    logging.getLogger("httpx").setLevel(logging.WARNING)  # one INFO line per request otherwise
    key, _ = load_credentials(cwd)
    return anthropic.Anthropic(api_key=key, max_retries=5, timeout=300.0)


def sdk_version() -> str:
    return str(anthropic.__version__)


@dataclass
class Call:
    """One Messages API call, as recorded in ``result.json``."""

    request_id: str
    model: str
    stop_reason: str
    usage: dict[str, Any]
    cost_usd: float
    wall_s: float
    stop_details: dict[str, Any] | None = None
    ratelimit: dict[str, str] = field(default_factory=dict)


@dataclass
class AgentRun:
    calls: list[Call] = field(default_factory=list)
    assistant_texts: list[str] = field(default_factory=list)
    tool_calls: list[str] = field(default_factory=list)
    final_text: str = ""
    stop_reason: str = ""
    hit_max_turns: bool = False
    classifier_refusal: bool = False
    error: str | None = None

    @property
    def turns(self) -> int:
        return len(self.calls)

    @property
    def cost_usd(self) -> float:
        return sum(c.cost_usd for c in self.calls)

    def usage(self) -> dict[str, int]:
        keys = ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")
        return {k: sum(int(c.usage.get(k) or 0) for c in self.calls) for k in keys}

    @property
    def subtype(self) -> str:
        if self.error:
            return "error_" + self.error
        if self.classifier_refusal:
            return "refusal"
        return "error_max_turns" if self.hit_max_turns else "success"

    def summary(self) -> dict[str, Any]:
        """Shape kept compatible with the Claude Code backend's ``result.json`` fields."""
        return {
            "result": {
                "subtype": self.subtype,
                "is_error": self.error is not None,
                "result": self.final_text,
                "num_turns": self.turns,
                "usage": self.usage(),
                "stop_reason": self.stop_reason,
                "cost_usd": round(self.cost_usd, 6),
            },
            "calls": [c.__dict__ for c in self.calls],
            "n_tool_calls": len(self.tool_calls),
            "classifier_refusal": self.classifier_refusal,
        }


def mcp_tools(app: FastMCP) -> list[dict[str, Any]]:
    """API tool definitions from the FastMCP server's tool list (no ``strict``: schemas stay as served)."""
    return [
        {"name": t.name, "description": t.description or "", "input_schema": t.inputSchema}
        for t in asyncio.run(app.list_tools())
    ]


def call_mcp_tool(app: FastMCP, name: str, args: dict[str, Any]) -> tuple[str, bool]:
    """(result text, is_error) exactly as the MCP server would return it."""
    try:
        out = asyncio.run(app.call_tool(name, args))
    except Exception as e:  # FastMCP raises ToolError for unknown tools and invalid arguments
        return str(e), True
    content = out[0] if isinstance(out, tuple) else out
    if isinstance(content, dict):
        return json.dumps(content, indent=2), False
    texts = [getattr(c, "text", "") for c in content]
    return "\n".join(t for t in texts if t), False


def _block_dict(b: Any) -> dict[str, Any]:
    d: dict[str, Any] = b.model_dump(mode="json", exclude_none=True)
    return d


def _create(
    client: anthropic.Anthropic, model: str, kwargs: dict[str, Any]
) -> tuple[anthropic.types.Message, dict[str, str], float]:
    t0 = time.monotonic()
    raw = client.messages.with_raw_response.create(model=model, **kwargs)
    msg = raw.parse()
    return msg, {k.lower(): str(v) for k, v in raw.headers.items()}, round(time.monotonic() - t0, 2)


def _record(msg: anthropic.types.Message, headers: dict[str, str], wall: float) -> Call:
    usage = msg.usage.model_dump(mode="json", exclude_none=True)
    sd = getattr(msg, "stop_details", None)
    return Call(
        request_id=headers.get("request-id", ""),
        model=msg.model,
        stop_reason=str(msg.stop_reason),
        usage=usage,
        cost_usd=round(call_cost(msg.model, usage), 8),
        wall_s=wall,
        stop_details=sd.model_dump(mode="json") if sd is not None else None,
        # the tier's limits only (not remaining/reset), to size --parallel
        ratelimit={
            k: v for k, v in headers.items() if k.startswith("anthropic-ratelimit-") and k.endswith("-limit")
        },
    )


def run_agent(
    client: anthropic.Anthropic,
    *,
    model: str,
    system: str,
    tools: list[dict[str, Any]],
    messages: list[dict[str, Any]],
    dispatch: Callable[[str, dict[str, Any]], tuple[str, bool]],
    max_turns: int,
    on_call: Callable[[Call], None] | None = None,
) -> AgentRun:
    """Append-only tool loop; ``messages`` is extended in place (assistant turns and tool results).

    One API response is one agent turn. If the cap is reached while the agent is still calling tools,
    those tool calls are executed (the agent issued them) and their results are left as the last user
    message, so a follow-up turn can be appended to it.
    """
    mid = model_id(model)
    run = AgentRun()
    for _ in range(max_turns):
        msg, headers, wall = _create(
            client,
            mid,
            {
                "max_tokens": MAX_TOKENS,
                "system": system,
                "tools": tools,
                "messages": messages,
                "output_config": {"effort": EFFORT[mid]},
                "cache_control": {"type": "ephemeral"},
            },
        )
        call = _record(msg, headers, wall)
        run.calls.append(call)
        if on_call:
            on_call(call)
        messages.append({"role": "assistant", "content": [_block_dict(b) for b in msg.content]})
        texts = [b.text for b in msg.content if b.type == "text" and b.text]
        run.assistant_texts += texts
        run.stop_reason = call.stop_reason
        if msg.stop_reason == "refusal":
            run.classifier_refusal = True
            return run
        if msg.stop_reason == "max_tokens":
            run.error = "max_tokens"
            return run
        uses = [b for b in msg.content if b.type == "tool_use"]
        if not uses:
            run.final_text = "\n".join(texts)
            return run
        results: list[dict[str, Any]] = []
        for u in uses:
            run.tool_calls.append(u.name)
            text, is_err = dispatch(u.name, dict(u.input))
            res: dict[str, Any] = {"type": "tool_result", "tool_use_id": u.id, "content": text}
            if is_err:
                res["is_error"] = True
            results.append(res)
        messages.append({"role": "user", "content": results})
    run.hit_max_turns = True
    run.final_text = "\n".join(run.assistant_texts[-1:])
    return run


def add_user_text(messages: list[dict[str, Any]], text: str) -> None:
    """Append a user turn; merge into a trailing tool-result message so roles keep alternating."""
    block = {"type": "text", "text": text}
    if messages and messages[-1]["role"] == "user":
        messages[-1]["content"] = [*messages[-1]["content"], block]
    else:
        messages.append({"role": "user", "content": [block]})


def _strict_schema(s: Any) -> Any:
    """Structured outputs need ``additionalProperties: false`` on every object."""
    if isinstance(s, dict):
        out = {k: _strict_schema(v) for k, v in s.items()}
        if out.get("type") == "object":
            out["additionalProperties"] = False
        return out
    if isinstance(s, list):
        return [_strict_schema(x) for x in s]
    return s


def structured(
    client: anthropic.Anthropic,
    *,
    model: str,
    system: str,
    user: str,
    schema: dict[str, Any],
    on_call: Callable[[Call], None] | None = None,
) -> tuple[dict[str, Any], Call]:
    """One no-tools call constrained to ``schema``; returns (parsed JSON, call record)."""
    mid = model_id(model)
    msg, headers, wall = _create(
        client,
        mid,
        {
            "max_tokens": MAX_TOKENS,
            "system": system,
            "messages": [{"role": "user", "content": user}],
            "output_config": {
                "effort": EFFORT[mid],
                "format": {"type": "json_schema", "schema": _strict_schema(schema)},
            },
        },
    )
    call = _record(msg, headers, wall)
    if on_call:
        on_call(call)
    text = next((b.text for b in msg.content if b.type == "text"), "")
    try:
        data: dict[str, Any] = json.loads(text) if msg.stop_reason == "end_turn" else {}
    except json.JSONDecodeError:
        data = {}
    return data, call
