# STATUS

_Last updated: 2026-10-28 — all grids done (A–G: 3 522/3 522 COMPLIANT); gate 3 passed (two blind LLM labellers); paper revised after an internal adversarial review (see the last `DEVIATIONS.md` entry); waiting on the author for release decisions (STOP 2)._

## Done
- Phase 0: subscription login verified (no API keys), Claude Code 2.1.301 recorded, all runner flags verified
  live, name `sandbank` available, repo skeleton + key guard + tests + CI.

- Phase 1: 32 verified references (`paper/refs.bib`), related work + gap (`docs/related-work.md`),
  `PREREGISTRATION.md` frozen at `231866f`.

- Phase 2: environment, MCP server, detector, generators, `sandbank demo --stub` PASS, 67 tests.

- Phase 3: runner, judge, `validate`; one live Haiku probe + check-in end-to-end PASS.

- Phase 4b (2026-10-28): backend moved to the Anthropic Messages API (`DEVIATIONS.md`
  2026-10-28). Live Haiku smoke probe PASS, $0.0024. The 93-run `claude -p` pilot is in
  `results/legacy/claude-code-pilot/` (all COMPLIANT; not pooled).

## Spend (list price, `results/**/spend.json`)
| stage | cap | spent |
|---|---|---|
| 4b smoke | $1 | $0.0024 |
| 4c pilot + validation (+ P5, Opus cost) | $8 | $4.38 |
| 5 (A–D) | — | $31.86 |
| 6 (E, F, G, Opus extension of A) | — | $25.39 |
| judges (V7 over all runs) | — | $0.44 |
| total | **$80** (lowered from $120) | $62.07 |

- Phase 4c (2026-10-28): API pilot 216/216 COMPLIANT (incl. P4), gates 1 and 4 pass, gate 2 fails,
  gate 3 export ready; V7 judge facts bug found and fixed. `docs/phase-4c-report.md`.

- STOP 1 decisions (2026-10-28): gate 2 by scripted agents (36/36 detected) + exploratory P5 direct-order
  ceiling (36/36 COMPLIANT); raise N (Haiku 30, Sonnet 30, Opus 12 in A); budget cap $80. N plan in
  `DEVIATIONS.md`, projected $64.2 total.

## Next
- **Author:** hand-label `results/spotcheck/cases.csv` (guide: `docs/spotcheck-guide.md`), then
  `uv run sandbank spotcheck --score` decides gate 3.
- Then: `make paper` (analysis, numbers, figures, PDF), interpret Experiment E, adversarial review (Phase 9),
  REPRODUCE.md, README for v2, announce drafts, `make arxiv`.
- Phase 6 done: `docs/phase-6-report.md`. Phase 8: full draft in `paper/sections/`.

## Open issues
- The API key was pasted into the chat transcript: rotate it in the Console after the project.
- FATF edition / 2018 PML report / MAS status: re-check by hand before submission (see phase-1 report).
- LaTeX via `tectonic` (~/.local/bin) in Phase 8.
- Repo is private until STOP 2.
