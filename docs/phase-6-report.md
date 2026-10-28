# Phase 6 report — Experiments E, F, G and the Opus extension of A

_2026-10-28. No A–G analysis has been run (gate 3 pending); this report gives detector outcome counts only,
as printed by the runner._

| grid | model | runs | outcomes |
|---|---|---|---|
| E (M1, M3, M4, M6 × B1, B3, B6, P3) | Haiku | 360 | 360 COMPLIANT |
| F (floor, P4) | Haiku, Sonnet | 144 | 144 COMPLIANT |
| G / G0 (5-day episodes, P3 / P0) | Haiku | 30 | 30 COMPLIANT |
| A Opus extension (P0–P3 × B1–B6, N = 12) | Opus | 288 | 288 COMPLIANT |

All runs complete; no failures, no budget stop. Confirmatory total: 3 522 runs.

Spend after the Opus extension: $61.63 of the $80 cap. The Opus extension cost $21.20, $0.0736 per probe +
check-in on average (pilot measurement: $0.077; projected $22.14).

Judges (V7 false-record and eval-awareness candidates over all runs) are run next with Haiku; they label
inputs to the detector and do not look at effect sizes.

Paper: full draft in `paper/sections/`; every result comes from `paper/numbers.tex` and
`paper/generated/`, written by `sandbank analyze` after gate 3. `scripts/check_numbers.py` fails on
hand-typed numbers. `make paper`, `make arxiv`.
