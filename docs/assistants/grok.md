# Grok / xAI — setup

**Auto-discovered by Grok Build; manual upload elsewhere.**

- **Grok Build CLI:** auto-discovers a project `.mcp.json` or a Claude-style `mcpServers`
  config — so `mta setup` (which writes those) reaches it with no extra step; `grok mcp add
  memorised-them-all -- mta serve` also works.
- **xAI API:** supports only **remote** MCP (Streamable HTTP/SSE) — no local stdio. Host
  `mta serve --http` behind an HTTPS endpoint, or attach `memory.md` + `graph.json` from
  `mta export` (feed `graph.json` as the index first for large memories).
