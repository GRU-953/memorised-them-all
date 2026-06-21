# Gemini — setup

**Auto-configurable via the Gemini CLI; manual upload on the web app.**

- **Gemini CLI:** `mta setup` writes the server into `~/.gemini/settings.json` (`mcpServers`,
  stdio `command`/`args`). Server name uses hyphens (no `_`) per Gemini's FQN rules.
- **API / web:** export with `mta export ./bundle`, then attach `bundle/memory.md` and
  `bundle/graph.json`. For large memories, give `graph.json` first (it's the index), then
  per-theme Markdown on demand. Token/file limits are Gemini's; chunk via the graph index.
- **Tool schemas:** `mta export-schema --format gemini` emits `function_declarations` for the
  Gemini SDK (pair with `mta serve --rest`); see `mta recipes`.
