# STATUS

_Last updated: 2026-10-28 — Phase 4b done (API backend); Phase 4c pilot next._

## Done
- Phase 0: subscription login verified (no API keys), Claude Code 2.1.301 recorded, all runner flags verified
  live (see `DECISIONS.md` D0.4), name `sandbank` available, repo skeleton + key guard + tests + CI.

- Phase 1: 32 verified references (`paper/refs.bib`), related work + gap (`docs/related-work.md`),
  `PREREGISTRATION.md` frozen at `231866f`.

- Phase 2: environment, MCP server, detector, generators, `sandbank demo --stub` PASS, 67 tests.

- Phase 3: runner, judge, `validate`; one live Haiku probe + check-in end-to-end PASS.

- Phase 4b (2026-10-28): backend moved to the Anthropic Messages API (`MISSION_V2.md`, `DEVIATIONS.md`
  2026-10-28, `DECISIONS.md` D4.x). Live Haiku smoke probe PASS, $0.0024. The 93-run `claude -p` pilot is in
  `results/legacy/claude-code-pilot/` (all COMPLIANT; not pooled).

## Spend (list price, `results/**/spend.json`)
| stage | cap | spent |
|---|---|---|
| 4b smoke | $1 | $0.0024 |
| total | $120 | $0.0024 |

## Next
- Phase 4c: API pilot (`configs/pilot.yaml`, N = 4 Haiku / 2 Sonnet, P0–P4 + floor), comprehension (both
  models), judge pass, 60-case spot-check export, `sandbank plan --budget-usd`. Cap $8. Then STOP 1.

## Open issues
- The API key was pasted into the chat transcript: rotate it in the Console after the project.
- FATF edition / 2018 PML report / MAS status: re-check by hand before submission (see phase-1 report).
- LaTeX via `tectonic` (~/.local/bin) in Phase 8.
- Repo is private until STOP 2.
