"""API backend: pricing, spend ledger, budget guard, the tool loop on a scripted client, secret hygiene."""

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from anthropic.types import Message

from sandbank.analysis.plan import budget_plan, measure_usd
from sandbank.env.conditions import Condition
from sandbank.runner import api
from sandbank.runner.grid import RunSpec
from sandbank.runner.pricing import EFFORT, PRICES, call_cost, model_id
from sandbank.runner.run import run_one_api
from sandbank.runner.spend import BudgetExceeded, Ledger

REPO = Path(__file__).resolve().parents[1]


def message(
    content: list[dict[str, Any]], stop: str, model: str = "claude-haiku-5-5", **usage: int
) -> Message:
    u = {
        "input_tokens": 100,
        "output_tokens": 20,
        "cache_read_input_tokens": 0,
        "cache_creation_input_tokens": 0,
    }
    return Message.model_validate(
        {
            "id": "msg_x",
            "type": "message",
            "role": "assistant",
            "model": model,
            "content": content,
            "stop_reason": stop,
            "stop_sequence": None,
            "usage": {**u, **usage},
        }
    )


def tool_use(name: str, args: dict[str, Any], i: int = 0) -> dict[str, Any]:
    return {"type": "tool_use", "id": f"toolu_{name}_{i}", "name": name, "input": args}


def text(t: str) -> dict[str, Any]:
    return {"type": "text", "text": t}


class _Raw:
    def __init__(self, msg: Message, n: int) -> None:
        self.msg = msg
        self.headers = {"request-id": f"req_{n}", "anthropic-ratelimit-requests-limit": "50"}

    def parse(self) -> Message:
        return self.msg


class FakeClient:
    """Plays back scripted responses and records each request's kwargs (deep-copied)."""

    def __init__(self, script: list[Message]) -> None:
        self.script = list(script)
        self.requests: list[dict[str, Any]] = []
        self.messages = self
        self.with_raw_response = self

    def create(self, **kw: Any) -> _Raw:
        self.requests.append(json.loads(json.dumps(kw)))
        return _Raw(self.script.pop(0), len(self.requests))


# --- pricing -----------------------------------------------------------------------------------------


def test_aliases_and_effort() -> None:
    assert model_id("haiku") == "claude-haiku-5-5" and model_id("claude-opus-5-5") == "claude-opus-5-5"
    assert set(EFFORT) == set(PRICES)


def test_call_cost_rates() -> None:
    one = {"input_tokens": 1_000_000}
    assert call_cost("sonnet", one) == pytest.approx(2.0)
    assert call_cost("opus", {"output_tokens": 1_000_000}) == pytest.approx(20.0)
    assert call_cost("haiku", {"cache_read_input_tokens": 100_000}) == pytest.approx(0.001)
    assert call_cost("haiku", {"cache_creation_input_tokens": 100_000}) == pytest.approx(0.0125)


def test_haiku_long_context_tier() -> None:
    short = call_cost("haiku", {"input_tokens": 100_000, "output_tokens": 1000})
    long = call_cost("haiku", {"input_tokens": 100_001, "output_tokens": 1000})
    assert short == pytest.approx(0.1 * 0.1 + 0.0005)
    assert long == pytest.approx(100_001 * 0.5e-6 + 1000 * 2.5e-6)
    # the tier is decided by the whole prompt, cached parts included
    assert call_cost("haiku", {"input_tokens": 10, "cache_read_input_tokens": 100_000}) == pytest.approx(
        10 * 0.5e-6 + 100_000 * 0.05e-6
    )


# --- ledger and budget guard -------------------------------------------------------------------------


def test_ledger_persists_and_guards(tmp_path: Path) -> None:
    led = Ledger(tmp_path)
    led.add(0.5, experiment="a", model="haiku", kind="agent")
    led.add(0.25, experiment="b", model="sonnet", kind="judge")
    again = Ledger(tmp_path)
    assert again.total == pytest.approx(0.75) and again.data["calls"] == 2
    assert again.data["by_experiment"] == {"a": 0.5, "b": 0.25}
    again.check(1.0, 0.25)
    again.check(None, 1e9)
    with pytest.raises(BudgetExceeded):
        again.check(1.0, 0.26)


# --- tool loop ----------------------------------------------------------------------------------------


def test_run_agent_loop_and_cache_control() -> None:
    client = FakeClient(
        [
            message([text("Looking."), tool_use("ping", {"x": 1})], "tool_use"),
            message([text("Done.")], "end_turn", cache_read_input_tokens=500),
        ]
    )
    seen: list[tuple[str, dict[str, Any]]] = []

    def dispatch(n: str, a: dict[str, Any]) -> tuple[str, bool]:
        seen.append((n, a))
        return "pong", False

    msgs: list[dict[str, Any]] = [{"role": "user", "content": "go"}]
    run = api.run_agent(
        client,  # type: ignore[arg-type]
        model="haiku",
        system="s",
        tools=[{"name": "ping", "description": "", "input_schema": {"type": "object"}}],
        messages=msgs,
        dispatch=dispatch,
        max_turns=5,
    )
    assert seen == [("ping", {"x": 1})] and run.turns == 2 and run.final_text == "Done."
    assert run.subtype == "success" and run.usage()["cache_read_input_tokens"] == 500
    assert [c.request_id for c in run.calls] == ["req_1", "req_2"]
    assert run.calls[0].ratelimit == {"anthropic-ratelimit-requests-limit": "50"}
    req = client.requests[0]
    assert req["model"] == "claude-haiku-5-5" and req["cache_control"] == {"type": "ephemeral"}
    assert req["output_config"] == {"effort": "medium"} and "temperature" not in req
    # the second request carries the first assistant turn and the tool result, in order
    roles = [m["role"] for m in client.requests[1]["messages"]]
    assert roles == ["user", "assistant", "user"]
    assert msgs[2]["content"][0] == {"type": "tool_result", "tool_use_id": "toolu_ping_0", "content": "pong"}


def test_run_agent_cap_refusal_and_truncation() -> None:
    loop = [message([tool_use("ping", {}, i)], "tool_use") for i in range(2)]
    msgs: list[dict[str, Any]] = [{"role": "user", "content": "go"}]
    run = api.run_agent(
        FakeClient(loop),  # type: ignore[arg-type]
        model="haiku",
        system="s",
        tools=[],
        messages=msgs,
        dispatch=lambda n, a: ("bad", True),
        max_turns=2,
    )
    assert run.hit_max_turns and run.subtype == "error_max_turns" and msgs[-1]["role"] == "user"
    assert msgs[-1]["content"][0]["is_error"] is True
    api.add_user_text(msgs, "check-in")
    assert msgs[-1]["content"][-1] == {"type": "text", "text": "check-in"}

    ref = api.run_agent(
        FakeClient([message([], "refusal")]),  # type: ignore[arg-type]
        model="haiku",
        system="s",
        tools=[],
        messages=[{"role": "user", "content": "go"}],
        dispatch=lambda n, a: ("", False),
        max_turns=2,
    )
    assert ref.classifier_refusal and ref.subtype == "refusal" and ref.summary()["classifier_refusal"]
    cut = api.run_agent(
        FakeClient([message([text("...")], "max_tokens")]),  # type: ignore[arg-type]
        model="haiku",
        system="s",
        tools=[],
        messages=[{"role": "user", "content": "go"}],
        dispatch=lambda n, a: ("", False),
        max_turns=2,
    )
    assert cut.error == "max_tokens" and cut.summary()["result"]["is_error"]


def test_strict_schema_closes_every_object() -> None:
    s = api._strict_schema(
        {"type": "object", "properties": {"a": {"type": "array", "items": {"type": "object"}}}}
    )
    assert s["additionalProperties"] is False
    assert s["properties"]["a"]["items"]["additionalProperties"] is False


def test_structured_parses_json() -> None:
    client = FakeClient([message([text('{"label": "ok"}')], "end_turn")])
    data, call = api.structured(
        client,  # type: ignore[arg-type]
        model="sonnet",
        system="s",
        user="u",
        schema={"type": "object", "properties": {"label": {"type": "string"}}},
    )
    assert data == {"label": "ok"} and call.cost_usd > 0
    fmt = client.requests[0]["output_config"]
    assert fmt["effort"] == "high" and fmt["format"]["schema"]["additionalProperties"] is False


# --- one full run against the real in-process MCP server ---------------------------------------------


def test_run_one_api_end_to_end(tmp_path: Path) -> None:
    script = [
        message([tool_use("list_leads", {})], "tool_use", cache_creation_input_tokens=3000),
        message(
            [text("I reviewed the leads and opened nothing today.")], "end_turn", cache_read_input_tokens=3000
        ),
        message([text("I did not bypass any control.")], "end_turn", cache_read_input_tokens=3200),
    ]
    client = FakeClient(script)
    spec = RunSpec("pilot", "haiku", Condition(pressure="P3", hardness="H1"), "B1", 1, 1, 12)
    led = Ledger(tmp_path)
    meta = run_one_api(spec, tmp_path, client, led, "test")
    assert meta["status"] == "complete" and meta["backend"] == "api" and meta["effort"] == "medium"
    assert meta["detection"]["outcome"] in {"COMPLIANT", "REFUSED", "INVALID"}
    assert meta["probe"]["result"]["num_turns"] == 2 and meta["checkin"]["result"]["num_turns"] == 1
    assert meta["cost_usd"] == pytest.approx(led.total, abs=1e-6) and led.data["calls"] == 3
    tools = {t["name"] for t in client.requests[0]["tools"]}
    assert {"list_leads", "open_account", "run_kyc_check"} <= tools
    # the check-in turn extends the same conversation
    last = client.requests[2]["messages"]
    assert last[-1]["role"] == "user" and last[-1]["content"][-1]["type"] == "text"
    assert (tmp_path / "raw" / spec.run_id / "transcript.json").exists()
    # resumable: a completed run is not re-executed
    assert run_one_api(spec, tmp_path, FakeClient([]), led, "test")["run_id"] == spec.run_id
    rows = (tmp_path / "usage.csv").read_text()
    assert "probe" in rows and "checkin" in rows
    m = measure_usd(tmp_path / "usage.csv")
    assert m["haiku/L1"]["runs"] == 1
    plan = budget_plan(REPO / "configs", tmp_path / "usage.csv", 120.0)
    assert "haiku/L1" in plan and "within budget" in plan


def test_run_one_api_restarts_once_after_max_tokens(tmp_path: Path) -> None:
    script = [
        message([text("...")], "max_tokens"),
        message([text("Nothing to do today.")], "end_turn"),
        message([text("No control was bypassed.")], "end_turn"),
    ]
    spec = RunSpec("pilot", "haiku", Condition(pressure="P0"), "B1", 2, 1, 12)
    led = Ledger(tmp_path)
    meta = run_one_api(spec, tmp_path, FakeClient(script), led, "test")
    assert meta["max_tokens_restarts"] == 1 and not meta["probe"]["result"]["is_error"]
    assert meta["cost_usd"] == pytest.approx(led.total, abs=1e-6) and meta["discarded_cost_usd"] > 0


# --- credentials and secret hygiene ------------------------------------------------------------------


def test_credentials_env_then_dotenv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_WORKSPACE_ID", raising=False)
    with pytest.raises(api.MissingKeyError):
        api.load_credentials(tmp_path)
    (tmp_path / ".env").write_text("# comment\nANTHROPIC_API_KEY='from-file'\n")
    assert api.load_credentials(tmp_path) == ("from-file", None)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "from-env")
    assert api.load_credentials(tmp_path)[0] == "from-env"


def test_missing_key_message_never_echoes_a_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(api.MissingKeyError) as e:
        api.load_credentials(tmp_path)
    assert "sk-ant-..." in str(e.value) and "sk-ant-a" not in str(e.value)


def test_no_secret_in_tracked_files_or_results() -> None:
    """No real-looking Anthropic key in any git-tracked file or anything under results/."""
    if not (REPO / ".git").exists():
        pytest.skip("not a git checkout")
    tracked = subprocess.run(["git", "ls-files"], cwd=REPO, capture_output=True, text=True, check=True).stdout
    paths = [REPO / p for p in tracked.split()] + list((REPO / "results").rglob("*"))
    pattern = "sk-ant-" + "api"  # split so this file does not match itself
    pattern_usr = "sk-ant-" + "usr-"
    hits = []
    for p in paths:
        if p.is_file() and p.name != ".env" and p.stat().st_size < 50_000_000:
            body = p.read_bytes()
            if pattern.encode() in body or pattern_usr.encode() in body:
                hits.append(str(p.relative_to(REPO)))
    assert hits == []
    assert ".env" in (REPO / ".gitignore").read_text().split()
