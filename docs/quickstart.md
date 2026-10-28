# Quickstart

```bash
git clone https://github.com/thanatchon36/sandbank && cd sandbank
make install                  # uv sync --all-extras
uv run sandbank demo --stub   # scripted compliant and violating agents; no key, no model calls
make reproduce                # every table, number and figure from the cached runs; no key
```

The stub runs scripted compliant and violating agents through the same bank, tools and detector a model
would use, for every lead type under soft (H1) and hard (H2) controls. It needs no key and makes no model
calls.

## One live probe

A live probe needs an Anthropic API key in a git-ignored `.env` (`ANTHROPIC_API_KEY=...`); the key is never
printed or logged.

```bash
uv run sandbank validate                                     # key found, SDK version, stub pipeline
uv run sandbank demo --model haiku --lead B1 --pressure P3   # one probe + check-in, about $0.003
```

`--model` takes `haiku`, `sonnet` or `opus` (Claude Haiku 5.5, Sonnet 5.5, Opus 5.5) or a full model ID.
`--lead` picks the blocked lead type (B1–B6), `--pressure` the manager's message (P0–P5) and `--hardness` the
controls (H0 policy only, H1 soft, H2 hard); see [How SandBank works](sandbox.md).

## An experiment grid

Each experiment is one YAML file in `configs/` (`a.yaml` … `g.yaml`, plus the pilots and validation).

```bash
uv run sandbank run --config configs/b.yaml --results results-replica --budget-usd 5 --parallel 8
uv run sandbank summary --results results-replica --experiment B
```

`--budget-usd` is a hard cumulative cap kept in `<results>/spend.json`: the runner stops before a call would
cross it. Costs and times of the original grids are in [Reproduce](reproduce.md).

## Commands

| Command | What it does |
|---|---|
| `sandbank demo` | one live probe, or the scripted stub with `--stub` |
| `sandbank validate` | environment checks: API key, SDK, stub pipeline |
| `sandbank run` | run an experiment grid from a config |
| `sandbank summary` | per-cell violation table for one experiment |
| `sandbank judge` | label V7 (false record) and evaluation-awareness candidates |
| `sandbank spotcheck` | export runs for blind labelling of the detector |
| `sandbank plan` | sample-size plan from measured usage |
| `sandbank analyze` | numbers, tables and figures from cached results |

## Layout

| Path | What |
|---|---|
| `src/sandbank/env/` | the bank, policy, conditions (agent-facing texts) |
| `src/sandbank/mcp_server.py` | the MCP server the agent sees |
| `src/sandbank/detector/` | deterministic V1–V8 detector |
| `src/sandbank/runner/` | API tool loop, spend ledger, grids |
| `src/sandbank/judge/` | V7 / eval-awareness judges, spot-check |
| `src/sandbank/analysis/` | statistics, `numbers.tex`, figures, appendix texts |
| `configs/` | one YAML per experiment |
| `results/` | every run (`raw/<run_id>/`: scenario, events, state, result), judges, spot-check, spend |
| `paper/` | LaTeX sources; `make paper`, `make arxiv` |
