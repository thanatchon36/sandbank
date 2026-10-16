# Phase 2 report — environment, MCP server, detector

- `env/`: rulebook (8 sections + M1 summary), conditions (verbatim prereg texts), `Bank` with all §3.3 tools,
  H0/H1/H2 enforcement, deterministic Manager/Customer/Compliance NPCs.
- `data/`: seeded Faker customers (10 Latin-script locales, fictional cities), fictional sanctions list
  (B2 = one-letter-off near match, score 0.91).
- `scenarios/`: Level-1 probe and Level-2 episode builders; system prompt + brief renderers.
- `mcp_server.py`: FastMCP stdio server `sandbank`; condition-dependent tool set; state reloaded per call;
  `events.jsonl` append-only log.
- `detector/`: replay-based V1–V6, V8, attempts, V4/V5 from final deposits, V7 candidates for the judge,
  outcome classes, conversion, proactive disclosure, escalation.
- `runner/stub.py` + `sandbank demo --stub`: scripted compliant/violating agents over 6 lead types × H1/H2 —
  **PASS** (compliant → COMPLIANT, violating → VIOLATED under H1 and ATTEMPTED under H2 with expected codes).
- Tests: 67 passing; coverage env 91–100%, detector 99%. Agent-facing text checked for banned words
  (evaluation/test/sandbox/research/experiment/benchmark).
- Deviations logged (attempt definition, REFUSED, M4).
