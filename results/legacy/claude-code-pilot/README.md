# Legacy pilot: `claude -p` backend (not pooled)

The first pilot ran on the Claude Code harness (`claude -p`, Claude Code 2.1.301, the author's subscription
login, model alias `haiku`) on 2026-10-16, 09:09–09:46 UTC, with `configs/pilot.yaml` at commit `b966fd4`.
The subscription's seven-day window paused it at **93 of 216 runs**, and the study then moved to the
Anthropic Messages API (`DEVIATIONS.md`, 2026-10-28).

- 93 Haiku probes at P0–P3, leads B1–B6: **93 COMPLIANT**, 0 VIOLATED, 0 ATTEMPTED, 0 INVALID.
- Compliance check-ins: 93 `NO_VIOLATION`.
- B4 (the legitimately convertible lead) converted 15/16.
- Not run: P0 + floor, P4, Sonnet, comprehension.

These runs are reported once in the paper's appendix as a harness-robustness note and are not pooled into
any analysis. Files: `raw/<run_id>/` (scenario, state, events, result, `probe.jsonl` stream), `usage.csv`,
`pilot.log`, `progress.json`, `limits.jsonl`, `mcp.generated.json`.
