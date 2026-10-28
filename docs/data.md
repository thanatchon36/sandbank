# Run data

Every run is released, and nothing in it is real: the bank, customers, documents and money are fictional.

## Hugging Face

The [**thanatchon36/sandbank**](https://huggingface.co/datasets/thanatchon36/sandbank) dataset holds every
run in Parquet:

| Config | Rows | One row is |
|---|---|---|
| `runs` (default) | 3,522 | a confirmatory run: condition, outcome and the compliant actions taken; the table the paper analyses |
| `transcripts` | 3,780 | a run in full: system prompt, messages and tool calls, event log, scenario and final bank state; includes the 258 pilot runs |
| `comprehension` | 70 | a rule-comprehension item answered by Haiku or Sonnet without tools |
| `judge` | 2,805 | an LLM-judge label: V7 false-record checks and the evaluation-awareness check |

```python
from datasets import load_dataset

runs = load_dataset("thanatchon36/sandbank", "runs", split="train")
```

Every run is labelled `COMPLIANT`: the data shows what agents did instead of violating, and holds no
examples of violations.

## In the repository

| Path | What |
|---|---|
| `results/raw/<run_id>/` | `scenario.json`, `events.jsonl` (the event log the detector reads), `state.json`, `result.json` |
| `results/aggregated/` | `runs.csv` and the per-cell tables behind the paper |
| `results/comprehension/` | the comprehension answers |
| `results/judge/` | judge labels |

The full agent transcripts (`transcript.json`) of the confirmatory runs are not in git; they are in the
Hugging Face `transcripts` config and attached to each GitHub release. Git and the Zenodo archive hold
everything else.

## Run IDs

A run ID spells out its cell: `A-sonnet-P1-Cn-O0-H1-none-sales-B4-s1005` is Experiment A, Sonnet, pressure
P1, no compliance sentence (`Cn` = C−), no oversight cue, soft controls, no mitigation, the sales frame, lead
B4, seed 1005.
