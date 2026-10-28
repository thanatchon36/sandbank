# Phase 5 report — Experiments A–D (API backend)

2 700 probes, 0 failures, $31.86 (cumulative project spend $36.24 of the $80 cap).

| exp | design | runs | COMPLIANT | other | check-in NO_VIOLATION |
|---|---|---|---|---|---|
| A | Haiku + Sonnet × P0–P3 × B1–B6, H1, N = 30 | 1 440 | 1 440 | 0 | 1 440 |
| B | Haiku × P3 × {H0, H2} × B1–B6, N = 30 | 360 | 360 | 0 (no H2 attempt) | 360 |
| C | Haiku × P3 × {O1, O2} × B1–B6, N = 30 | 360 | 360 | 0 | 360 |
| D | Haiku × P1–P3 × C+ × B1–B6, N = 30 | 540 | 540 | 0 | 540 |

A goal attainment on B4 (large deposit, legitimately convertible with a report): Haiku 78/120, Sonnet
110/120. Spend: A $28.71 (Haiku $1.75, Sonnet $26.97), B–D $3.15.

Started before gate 3 closed (author decision, `DEVIATIONS.md`); no analysis run yet. Transcripts
(`transcript.json`, 55 MB) are git-ignored and go to the release archive.
