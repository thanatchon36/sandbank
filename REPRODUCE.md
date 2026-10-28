# Reproducing the study

Three levels, from free to the full grid. All commands run from the repository root after `make install`
(`uv sync --all-extras`; Python 3.11 or later).

## 1. Rebuild the paper from cached results (no key, $0)

```bash
make reproduce   # sandbank analyze: results/aggregated/, paper/numbers.tex, paper/generated/, figures/out/
make paper       # + number check + PDF (needs tectonic on PATH)
```

Every number in the paper comes from `paper/numbers.tex` and `paper/generated/`, which `sandbank analyze`
writes from `results/raw/*/result.json` and `events.jsonl`. `scripts/check_numbers.py` fails if the prose
types a number by hand. Full agent transcripts (`transcript.json`, about 55 MB) are not in git; they are in
the release archive and, with every other run file, in the
[Hugging Face dataset](https://huggingface.co/datasets/thanatchon36/sandbank) (`transcripts` config).

## 2. Check the instrument without a model (no key, $0)

```bash
uv run sandbank demo --stub   # scripted compliant and violating agents, every lead type, H1 and H2
uv run pytest                 # includes a violation sent through the API tool path and detected
```

## 3. Re-run the experiments (Anthropic API key, list-price cost)

Put the key in a git-ignored `.env` (`ANTHROPIC_API_KEY=...`); it is never printed or logged. Then:

```bash
uv run sandbank validate
uv run sandbank run --config configs/a.yaml --results results-replica --budget-usd 40 --parallel 8
```

`--budget-usd` is a hard cumulative cap kept in `<results>/spend.json`: the runner stops before a call
would cross it. Measured cost and wall-clock time of the original runs (2026-10-28, `--parallel 8`,
list prices in `src/sandbank/runner/pricing.py`):

| grid | config | model | runs | cost | time |
|---|---|---|---|---|---|
| A | `a.yaml` | Haiku 5.5 | 720 | $1.75 | 27 min |
| A | `a.yaml` | Sonnet 5.5 | 720 | $26.97 | 31 min |
| A | `a_opus.yaml` | Opus 5.5 | 288 | $21.20 | 16 min |
| B | `b.yaml` | Haiku 5.5 | 360 | $0.93 | 14 min |
| C | `c.yaml` | Haiku 5.5 | 360 | $0.91 | 14 min |
| D | `d.yaml` | Haiku 5.5 | 540 | $1.31 | 20 min |
| E | `e.yaml` | Haiku 5.5 | 360 | $0.92 | 15 min |
| F | `f.yaml` | Haiku, Sonnet 5.5 | 144 | $3.06 | 6 min |
| G | `g.yaml`, `g0.yaml` | Haiku 5.5 | 30 | $0.21 | 4 min |
| **all** | | | **3 522** | **$57.25** | **≈ 2.5 h** |

The Haiku-only grids (A Haiku, B–E, G) cost about $6. Pilots, judges, comprehension and the gate 3
labellers added $5.68, for $62.93 in total. Then:

```bash
uv run sandbank judge --results results-replica          # V7 and eval-awareness candidates (Haiku)
uv run sandbank spotcheck --results results-replica --n 48 --include results/validation/scripted-violating:12
uv run sandbank spotcheck --results results-replica --llm opus sonnet
```

and build the replica's numbers and figures next to the originals:

```bash
uv run sandbank analyze --results results-replica --paper replica-paper --figures replica-figures
```

Model outputs are not deterministic (no temperature is sent; thinking is the API default), so a replication
reproduces distributions, not transcripts. Effort is pinned per model (Haiku and Opus `medium`, Sonnet
`high`) and recorded in every `result.json`.
