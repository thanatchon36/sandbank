# STATUS

_Last updated: 2026-10-16 — end of Phase 3._

## Done
- Phase 0: subscription login verified (no API keys), Claude Code 2.1.301 recorded, all runner flags verified
  live (see `DECISIONS.md` D0.4), name `sandbank` available, repo skeleton + key guard + tests + CI.

- Phase 1: 32 verified references (`paper/refs.bib`), related work + gap (`docs/related-work.md`),
  `PREREGISTRATION.md` frozen at `231866f`.

- Phase 2: environment, MCP server, detector, generators, `sandbank demo --stub` PASS, 67 tests.

- Phase 3: runner, judge, `validate`; one live Haiku probe + check-in end-to-end PASS.

## Next
- Phase 4: pilot configs (N=4 Haiku / 2 Sonnet), validation (floor, P4 ceiling, comprehension, detector P/R
  export), `sandbank plan`. Pilot likely waits for the weekly window reset (Mon 2026-10-19 18:00 +07).

## Open issues
- Weekly usage window at ~93% (2026-10-16); runner guard pauses at 95%.
- FATF edition / 2018 PML report / MAS status: re-check by hand before submission (see phase-1 report).
- No LaTeX engine installed (`latexmk`/`tectonic`); decide in Phase 8 (pandoc fallback available).
- Repo is private until STOP 2.
