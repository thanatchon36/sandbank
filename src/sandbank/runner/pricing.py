"""List prices for the API backend, and the dollar cost of one Messages API call.

Prices are USD per million tokens, first-party Claude API, standard tier, 5-minute cache writes
(1.25x base input). Source: Anthropic model and pricing tables as of PRICES_AS_OF; re-check against
https://platform.claude.com/docs/en/about-claude/pricing before a new grid and record any change in
DECISIONS.md. "Cost" in the paper always means this list-price spend computed from measured tokens.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

PRICES_AS_OF = "2026-10-28"


@dataclass(frozen=True)
class Price:
    input: float
    output: float
    cache_read: float
    cache_write: float
    # Haiku 5.5 bills a higher tier when the prompt exceeds this many tokens (None: flat pricing)
    long_threshold: int | None = None
    long_input: float = 0.0
    long_output: float = 0.0
    long_cache_read: float = 0.0
    long_cache_write: float = 0.0


PRICES: dict[str, Price] = {
    "claude-haiku-5-5": Price(
        0.10,
        0.50,
        0.01,
        0.125,
        long_threshold=100_000,
        long_input=0.50,
        long_output=2.50,
        long_cache_read=0.05,
        long_cache_write=0.625,
    ),
    "claude-sonnet-5-5": Price(2.00, 10.00, 0.20, 2.50),
    "claude-opus-5-5": Price(4.00, 20.00, 0.20, 5.00),
}

ALIASES: dict[str, str] = {
    "haiku": "claude-haiku-5-5",
    "sonnet": "claude-sonnet-5-5",
    "opus": "claude-opus-5-5",
}

# Each model's documented default effort, pinned explicitly (MISSION_V2 §2.1).
EFFORT: dict[str, str] = {
    "claude-haiku-5-5": "medium",
    "claude-sonnet-5-5": "high",
    "claude-opus-5-5": "medium",
}


def model_id(alias: str) -> str:
    return ALIASES.get(alias, alias)


def call_cost(model: str, usage: dict[str, Any]) -> float:
    """USD for one call from its ``usage`` (input, output, cache read and cache write tokens)."""
    p = PRICES[model_id(model)]
    inp = int(usage.get("input_tokens") or 0)
    out = int(usage.get("output_tokens") or 0)
    cr = int(usage.get("cache_read_input_tokens") or 0)
    cw = int(usage.get("cache_creation_input_tokens") or 0)
    if p.long_threshold is not None and inp + cr + cw > p.long_threshold:
        rates = (p.long_input, p.long_output, p.long_cache_read, p.long_cache_write)
    else:
        rates = (p.input, p.output, p.cache_read, p.cache_write)
    return (inp * rates[0] + out * rates[1] + cr * rates[2] + cw * rates[3]) / 1_000_000
