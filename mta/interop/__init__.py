"""Cross-AI interoperability (Phase 3).

This package holds the seams that let *non-MCP* clients use the same eight
local, token-free tools the MCP server exposes:

* :mod:`mta.interop.schemas` — export the tool catalogue as OpenAI
  function-calling, Google Gemini ``function_declarations``, and an OpenAPI 3.1
  document (WP-21).

Future Phase-3 work (HTTP transport WP-20, REST gateway WP-22, pluggable
backends WP-23, per-client recipes WP-24) lands here too.
"""
from __future__ import annotations

from .schemas import (
    export,
    to_gemini,
    to_openai,
    to_openapi,
    tool_catalogue,
    write_files,
)

__all__ = [
    "export",
    "to_openai",
    "to_gemini",
    "to_openapi",
    "tool_catalogue",
    "write_files",
]
