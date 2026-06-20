"""WP-24 — per-client connection recipes for every surface.

One place that renders ready-to-paste setup for the clients people actually use,
composed off the seams the rest of Phase 3 already exposes:
:func:`mta.transport.client_config` (HTTP MCP), :func:`mta.interop.rest.client_recipe`
(REST), and :mod:`mta.interop.schemas` (OpenAI / Gemini / OpenAPI). Printed by
``mta recipes``.

Pure and offline: it only formats strings/dicts (a *placeholder* token unless one is
supplied — it never resolves or writes a real token) — no server, no network, nothing
through the model.
"""
from __future__ import annotations

import json

from ..core.config import Config, load as load_config

TOKEN_PLACEHOLDER = "<TOKEN-from-the-`mta serve --http|--rest`-banner>"


def build(cfg: Config | None = None, *, host: str | None = None, port: int | None = None,
          path: str | None = None, token: str | None = None) -> dict:
    """Return a structured recipe set for every client surface."""
    cfg = cfg or load_config()
    host = host or cfg.http_host
    port = int(port or cfg.http_port)
    path = "/" + (path or cfg.http_path).strip().lstrip("/")
    tok = token or TOKEN_PLACEHOLDER

    from ..transport import client_config
    from .rest import client_recipe
    from .schemas import tool_catalogue

    http = client_config(host, port, path, tok)
    rest = client_recipe(host, port, tok)
    base = rest["base_url"]

    return {
        "tools": len(tool_catalogue()),  # derive from the single source → never drifts
        "surfaces": {
            "auto": {
                "description": "One command auto-configures every detected stdio MCP client "
                               "(Claude Desktop/Code, Gemini CLI, Cursor, VS Code, Windsurf, "
                               "OpenAI Codex). Idempotent, with a per-file backup.",
                "command": "mta setup",
                "dry_run": "mta setup --dry-run",
                "note": "Grok Build auto-discovers the Claude/.mcp.json config, so it's covered too. "
                        "The ChatGPT app and the xAI API accept only REMOTE MCP — use the http_mcp/rest "
                        "surfaces below and paste the URL into their UI.",
            },
            "stdio": {
                "description": "Default. Claude Desktop / Claude Code launch the server over stdio (no token needed).",
                "claude_code": "claude mcp add memorised-them-all -- mta serve",
                "claude_desktop": "Install the .mcpb from the GitHub Release (one click), "
                                  "or add the mcp_json below to your client config.",
                "mcp_json": {"mcpServers": {"memorised-them-all": {"command": "mta", "args": ["serve"]}}},
            },
            "http_mcp": {
                "description": "MCP over Streamable HTTP, for remote / non-stdio MCP clients.",
                "start": "mta serve --http",
                "url": http["url"],
                "claude_code": http["claude_code_add"],
                "mcp_json": {"mcpServers": http["mcp_json"]},
                "health": http["health"],
            },
            "rest": {
                "description": "Plain JSON for non-MCP clients (curl, scripts, OpenAPI SDKs).",
                "start": "mta serve --rest",
                "base_url": base,
                "openapi": rest["openapi"],
                "curl": rest["curl_example"],
            },
            "openai": {
                "description": "Use the tools from the OpenAI SDK via function calling + the REST gateway.",
                "schema": "mta export-schema --format openai > tools.json",
                "how": "Pass tools=json.load(open('tools.json')) to chat.completions; for each "
                       f"tool_call, POST its JSON arguments to {base}/tools/<name> (with the bearer "
                       "token) and feed the result back as the tool message.",
            },
            "gemini": {
                "description": "Use the tools from the Gemini SDK via function declarations + the REST gateway.",
                "schema": "mta export-schema --format gemini > gemini.json",
                "how": "Pass the function_declarations from gemini.json as a Tool; execute each "
                       f"function_call by POSTing to {base}/tools/<name>.",
            },
        },
        "notes": [
            "stdio is the default and needs no token. `--http` / `--rest` print a bearer token on "
            "start (the two share one token); paste it where <TOKEN> appears.",
            "Every surface exposes the SAME token-free tools and returns the same results.",
        ],
    }


def render_text(data: dict) -> str:
    """Human-readable rendering of :func:`build`."""
    out = ["Memorised them All — connection recipes",
           f"  ({data['tools']} token-free tools, identical across every surface)", ""]
    for name, surface in data["surfaces"].items():
        out.append(f"== {name} ==")
        out.append(f"  {surface.get('description', '')}")
        for key, val in surface.items():
            if key == "description":
                continue
            if isinstance(val, (dict, list)):
                val = json.dumps(val)
            out.append(f"  {key}: {val}")
        out.append("")
    for note in data.get("notes", []):
        out.append(f"• {note}")
    return "\n".join(out)
