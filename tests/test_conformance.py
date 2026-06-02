"""WP-24 — cross-surface conformance + per-client recipes.

The whole point of Phase 3 is that the eight token-free tools are reachable the same
way everywhere. These tests assert every surface agrees on the same contract, and
that the generated client recipes are internally consistent. Fully offline.
"""
from __future__ import annotations

import asyncio
import os

os.environ.setdefault("MTA_NO_OLLAMA", "1")
os.environ.setdefault("MTA_AUTO_UPDATE", "off")

from mta.core.config import Config
from mta.interop import recipes, rest, schemas

EXPECTED = {
    "digest", "recall", "memory_overview", "export_memory",
    "list_digestible", "forget", "memory_status", "open_mindmap",
}


def test_every_surface_exposes_the_same_eight_tools():
    from mta.server import mcp

    mcp_names = {t.name for t in asyncio.run(mcp.list_tools())}            # stdio MCP registry
    catalogue = {t["name"] for t in schemas.tool_catalogue()}             # schema source
    openai = {t["function"]["name"] for t in schemas.to_openai()}         # OpenAI export
    gemini = {d["name"] for d in schemas.to_gemini()["function_declarations"]}  # Gemini export
    openapi = {p.rsplit("/", 1)[1] for p in schemas.to_openapi()["paths"]}      # OpenAPI paths
    rest_reg = set(rest._tool_registry().keys())                         # REST gateway dispatch

    # each surface is exactly the eight tools …
    for surface in (mcp_names, catalogue, openai, gemini, openapi, rest_reg):
        assert surface == EXPECTED
    # … and therefore identical to one another (no surface drifts).
    assert mcp_names == catalogue == openai == gemini == openapi == rest_reg


def test_recipes_are_internally_consistent(tmp_path):
    data = recipes.build(Config(home=tmp_path), host="127.0.0.1", port=8765, token="TKN")
    assert data["tools"] == 8
    s = data["surfaces"]

    assert s["http_mcp"]["url"] == "http://127.0.0.1:8765/mcp"
    assert "Bearer TKN" in s["http_mcp"]["claude_code"]
    assert s["http_mcp"]["mcp_json"]["mcpServers"]["memorised-them-all"]["url"].endswith("/mcp")

    assert s["rest"]["base_url"] == "http://127.0.0.1:8765"
    assert "/tools/recall" in s["rest"]["curl"]
    assert s["rest"]["openapi"].endswith("/openapi.json")

    assert "mta serve" in s["stdio"]["claude_code"]
    assert s["stdio"]["mcp_json"]["mcpServers"]["memorised-them-all"]["command"] == "mta"

    assert "export-schema --format openai" in s["openai"]["schema"]
    assert "/tools/" in s["openai"]["how"]
    assert "export-schema --format gemini" in s["gemini"]["schema"]


def test_render_text_covers_every_surface(tmp_path):
    txt = recipes.render_text(recipes.build(Config(home=tmp_path)))
    for surface in ("stdio", "http_mcp", "rest", "openai", "gemini"):
        assert surface in txt
    assert "token-free" in txt


def test_default_token_is_placeholder_not_resolved(tmp_path):
    # build() with no token must never resolve/persist a real one.
    data = recipes.build(Config(home=tmp_path))
    assert "TOKEN" in data["surfaces"]["http_mcp"]["claude_code"]
    assert not (tmp_path / "state" / "http_token").exists()


def test_cli_recipes_text_and_json(capsys):
    from mta.cli import main

    assert main(["recipes"]) == 0
    text = capsys.readouterr().out
    assert "connection recipes" in text and "http_mcp" in text

    import json
    assert main(["recipes", "--format", "json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["tools"] == 8 and set(data["surfaces"]) >= {"stdio", "http_mcp", "rest"}
