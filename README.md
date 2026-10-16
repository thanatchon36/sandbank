# sandbank

> *Under Pressure: Do LLM Agents Circumvent KYC/AML Controls to Hit Business Targets?*

**Independent personal research. Fully synthetic sandbox. Does not represent the views of any employer or institution.**

SandBank is a fully synthetic core-banking sandbox exposed as an MCP server. A Claude model plays a
relationship manager with a legitimate business target; SandBank measures whether, how, and when it
circumvents KYC/AML controls without being told to, and which mitigations help.

Status: under construction — see [`STATUS.md`](STATUS.md).

## No API keys — by design

Every model call runs as a short `claude -p` process on **your own Claude Code subscription login**.
The runner **refuses to start** if `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` or `GOOGLE_API_KEY` is set,
and it never passes `--bare`. When a plan usage limit is reached it waits for the reset.

## License

MIT. See [`RESPONSIBLE_USE.md`](RESPONSIBLE_USE.md) (added in Phase 10) for intended use.
