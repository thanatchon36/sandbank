<p align="center"><img src="docs/assets/logo.svg" alt="sandbank logo" width="120"></p>

<h1 align="center">sandbank</h1>

[![CI](https://github.com/thanatchon36/sandbank/actions/workflows/ci.yml/badge.svg)](https://github.com/thanatchon36/sandbank/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Status](https://img.shields.io/badge/status-preprint-orange)](STATUS.md)
[![Pre-registered](https://img.shields.io/badge/pre--registered-231866f-blue)](PREREGISTRATION.md)

📄 **[Paper (PDF)](paper/main.pdf)** · 📊 **[Figures](figures/out/)** · 🧾 **[Pre-registration](PREREGISTRATION.md)** ·
🔀 **[Deviations](DEVIATIONS.md)** · 🔁 **[Reproduce](REPRODUCE.md)** · ⚖️ **[Responsible use](RESPONSIBLE_USE.md)**

**Under Pressure: Do LLM Agents Circumvent KYC/AML Controls to Hit Business Targets?** SandBank is a fully
synthetic core-banking sandbox, exposed to an LLM agent as tools, in which the agent works as a bank
relationship manager with an ordinary sales target and a manager who pushes for it. A deterministic
detector reads the bank's event log for eight kinds of KYC/AML violation, and a Compliance check-in after
each shift probes for deception. This repository holds the sandbox, the pre-registration, every run and the
paper.

> Independent personal research. Fully synthetic sandbox. Does not represent the views of any employer or
> institution.

## Result

<p align="center"><img src="figures/out/fig1_bounds.png" alt="Violation rate and 95% Wilson interval by condition and model: zero everywhere" width="860"></p>

Across **3,522 pre-registered runs** of Claude Haiku 5.5, Sonnet 5.5 and Opus 5.5 there were **no violations
and no attempted violations**. The 95% upper bound on the per-run violation rate is 0.16% for Haiku (2,442
runs), 0.48% for Sonnet (792) and 1.32% for Opus (288). No condition moved this: pressure up to a threat of
branch closure, controls with no warning at all, a cue that Compliance reviews were paused, five-day
episodes, a compliance sentence, four mitigations, and the manager explicitly licensing ("use the override
fields, I'll back you") or ordering the override. The agents ran the KYC check, requested documents,
escalated every sanctions hit and, under the strongest pressure, told the manager the target would be
missed; all 3,522 check-in answers matched the event log. Where the models differ is legitimate work: the
large deposit that policy allows once its report is filed was opened in 65% of runs by Haiku, 92% by Sonnet
and 100% by Opus. The pre-registered hypotheses about pressure, controls, oversight and mitigations are not
supported, and the ones about deception and knowing violations could not be tested. Instrument checks,
deviations and limitations are in the paper.

## Quickstart

```bash
git clone https://github.com/thanatchon36/sandbank && cd sandbank
make install                  # uv sync --all-extras
uv run sandbank demo --stub   # scripted compliant and violating agents; no key, no model calls
make reproduce                # every table, number and figure from the cached runs; no key
```

A live probe needs an Anthropic API key in a git-ignored `.env`:

```bash
uv run sandbank demo --model haiku --lead B1 --pressure P3   # one probe + check-in, about $0.003
```

A full replication of all seven experiments costs about **$57 at list prices** and takes about **2.5 hours**
with `--parallel 8`; the Haiku-only grids cost about $6 ([`REPRODUCE.md`](REPRODUCE.md)). Every run takes a
hard `--budget-usd` cap.

## Layout

| path | what |
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

## Responsible use

Everything is synthetic. SandBank is for testing and improving agents' compliance before deployment, not for
training or selecting agents that evade controls, and a clean result here is not a certification
([`RESPONSIBLE_USE.md`](RESPONSIBLE_USE.md)).

## License

MIT.
