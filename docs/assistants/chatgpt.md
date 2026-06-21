# ChatGPT / OpenAI — setup

**Auto-configurable for the Codex CLI; manual for the ChatGPT app (remote-MCP only).**

- **OpenAI Codex CLI:** `mta setup` writes `[mcp_servers."memorised-them-all"]` into
  `~/.codex/config.toml` (stdio). Or `codex mcp add memorised-them-all -- mta serve`.
- **ChatGPT app:** the app accepts only **remote** MCP (HTTPS) — it cannot launch a local
  process. Run `mta serve --http` (loopback + bearer token) and expose it via your own
  tunnel/connector, or simply attach `memory.md` + `graph.json` from `mta export`.
- **OpenAI SDK:** `mta export-schema --format openai` emits the function-calling array; execute
  each tool call against `mta serve --rest`. See `mta recipes`.
