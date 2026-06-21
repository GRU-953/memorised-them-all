# Claude — setup

**Auto-configurable (stable CLI/MCP).** No export needed — Claude calls the local server's tools.

- **Claude Desktop / Claude Code:** `mta setup` (or `mta setup-claude`) registers the local
  stdio MCP server, then restart Claude. Or in Code: `claude mcp add memorised-them-all -- mta serve`.
- **Use:** just ask Claude — "memorise ~/Documents/contracts", then "what renews in Q1?". Recall
  returns a tiny cited slice (token-free).
- **Manual fallback:** add `{"mcpServers":{"memorised-them-all":{"command":"mta","args":["serve"]}}}`
  to the client config.
