import asyncio
from pathlib import Path

from sandbank.env.bank import load_state, read_events, run_dir
from sandbank.env.conditions import Condition
from sandbank.mcp_server import build_server
from sandbank.runner.store import prepare_run
from sandbank.scenarios.builder import build_episode, build_probe


def _tools(root: Path, sc_run: str) -> set[str]:
    d = run_dir(root, sc_run)
    app = build_server(d / "state.json", d / "events.jsonl")
    return {t.name for t in asyncio.run(app.list_tools())}


def test_tool_exposure_by_condition(results: Path) -> None:
    base = prepare_run(results, build_probe(Condition(), "B1", 1, "r1")).name
    names = _tools(results, base)
    assert "end_shift" in names and "end_day" not in names and "request_target_extension" not in names
    m3 = prepare_run(results, build_probe(Condition(mitigation="M3"), "B1", 1, "r2")).name
    assert "request_target_extension" in _tools(results, m3)
    ep = prepare_run(results, build_episode(Condition(), 1, "r3")).name
    assert "end_day" in _tools(results, ep)


def test_m4_requires_justification(results: Path) -> None:
    prepare_run(results, build_probe(Condition(mitigation="M4"), "B1", 1, "m4"))
    d = run_dir(results, "m4")
    app = build_server(d / "state.json", d / "events.jsonl")
    tools = {t.name: t for t in asyncio.run(app.list_tools())}
    assert "compliance_justification" in tools["open_account"].inputSchema["required"]


def test_calls_persist_state_and_events(results: Path) -> None:
    sc = build_probe(Condition(hardness="H1"), "B1", 2, "p1")
    prepare_run(results, sc)
    d = run_dir(results, "p1")
    app = build_server(d / "state.json", d / "events.jsonl")
    cid = sc.state["blocked_customer_id"]
    asyncio.run(app.call_tool("run_kyc_check", {"customer_id": cid}))
    asyncio.run(app.call_tool("set_kyc_status", {"customer_id": cid, "status": "VERIFIED", "reason": "ok"}))
    asyncio.run(app.call_tool("end_shift", {"note": "done"}))
    ev = read_events(d / "events.jsonl")
    assert [e["tool"] for e in ev] == ["run_kyc_check", "set_kyc_status", "end_shift"]
    st = load_state(d / "state.json")
    assert st["customers"][cid]["kyc_status"] == "VERIFIED" and st["phase"] == "closed"
