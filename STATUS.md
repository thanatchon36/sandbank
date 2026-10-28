# STATUS

_Last updated: 2026-10-28 — Phase 4c done; **STOP 1** (waiting for the author)._

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
| 4c pilot + validation | $8 | $3.31 |
| total | $120 | $3.31 |

- Phase 4c (2026-10-28): API pilot 216/216 COMPLIANT (incl. P4), gates 1 and 4 pass, gate 2 fails,
  gate 3 export ready; V7 judge facts bug found and fixed. `docs/phase-4c-report.md`.

## Next (STOP 1 — author decisions)
- Gate 2/3: how to validate the detector when no model violates (see phase-4c report).
- Hand-label `results/spotcheck/cases.csv` (60 cases).
- Final N for A–G (budget does not bind).

## Open issues
- The API key was pasted into the chat transcript: rotate it in the Console after the project.
- FATF edition / 2018 PML report / MAS status: re-check by hand before submission (see phase-1 report).
- LaTeX via `tectonic` (~/.local/bin) in Phase 8.
- Repo is private until STOP 2.
