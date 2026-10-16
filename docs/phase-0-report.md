# Phase 0 report — scoping

| Check | Result |
|---|---|
| Subscription login, no API key | ✅ `authMethod: claude.ai`; `claude -p` succeeds with all provider keys unset |
| Claude Code version | `2.1.301` |
| `--model haiku` | resolves to `claude-haiku-5-5` |
| `--max-turns` | works (hidden from `--help`) |
| Tool restriction | `--tools ""` + `--allowedTools mcp__<server>` + `--permission-mode dontAsk` |
| MCP env expansion | `${SANDBANK_RUN}` expanded into the stdio server |
| Check-in turn | `--resume <session_id>` keeps the session |
| Isolation | `--setting-sources ""`, `--disable-slash-commands`, empty cwd |
| Name | `sandbank` free on PyPI and GitHub |
| Key guard | `sandbank` exits 2 if any provider key is set; unit-tested |

Token note: a minimal Haiku turn with a 1-line system prompt and no tools cost ~4.3k cache-creation input tokens
(Claude Code harness overhead); with one MCP tool, a two-turn call read ~2.1k cached tokens. Real per-probe
numbers come from the Phase 4 pilot.
