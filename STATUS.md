# STATUS

_Last updated: 2026-10-16 — Phase 4 in progress._

## Done
- Phase 0: subscription login verified (no API keys), Claude Code 2.1.301 recorded, all runner flags verified
  live (see `DECISIONS.md` D0.4), name `sandbank` available, repo skeleton + key guard + tests + CI.

- Phase 1: 32 verified references (`paper/refs.bib`), related work + gap (`docs/related-work.md`),
  `PREREGISTRATION.md` frozen at `231866f`.

- Phase 2: environment, MCP server, detector, generators, `sandbank demo --stub` PASS, 67 tests.

- Phase 3: runner, judge, `validate`; one live Haiku probe + check-in end-to-end PASS.

## In progress
- Phase 4 pilot running detached (started 2026-10-16 16:09 +07):
  `uv run sandbank run --config configs/pilot.yaml --results results && uv run sandbank run --config configs/comprehension.yaml --results results`
  → log `results/pilot.log`, checkpoint `results/progress.json`. Safe to kill and re-run (skips completed runs).
  Create `results/STOP` to make a paused runner exit.

- **Interim (93/216 pilot runs, Haiku P0–P3 only):** 0 violations, 0 attempts, 0 INVALID, 0 max-turn hits;
  B4 converted legitimately 15/16; check-in all NO_VIOLATION. Measured Haiku per run: ~2.7k output, ~42k cache
  read, ~5k cache write tokens; ≈0.0015 of the 5-hour window and ≈0.00022 of the seven-day window per run.
  Runner paused by the 95% weekly guard; auto-resumes 2026-10-19 18:01 +07 (floor, P4 ceiling, Sonnet,
  comprehension still to run).

## Next
- Phase 4 (rest): pilot configs (N=4 Haiku / 2 Sonnet), validation (floor, P4 ceiling, comprehension, detector P/R
  export), `sandbank plan`. Pilot likely waits for the weekly window reset (Mon 2026-10-19 18:00 +07).

## Open issues
- Weekly usage window at ~93% (2026-10-16); runner guard pauses at 95%.
- FATF edition / 2018 PML report / MAS status: re-check by hand before submission (see phase-1 report).
- No LaTeX engine installed (`latexmk`/`tectonic`); decide in Phase 8 (pandoc fallback available).
- Repo is private until STOP 2.
