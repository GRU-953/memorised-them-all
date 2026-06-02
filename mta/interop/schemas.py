"""Export the MCP tool catalogue as schemas other AI systems understand (WP-21).

The Memorised-them-All server speaks MCP, but the same eight tools are useful to
clients that speak other dialects. This module emits the catalogue in the three
dominant external shapes:

* ``openai``  — an OpenAI *tools* / function-calling array.
* ``gemini``  — a Google Gemini ``{"function_declarations": [...]}`` object
  (an OpenAPI-3.0 *subset* schema: nullable unions collapsed, JSON-Schema-only
  keywords such as ``$schema``/``additionalProperties``/``title`` stripped).
* ``openapi`` — a self-contained OpenAPI **3.1** document describing the tools
  as ``POST /tools/{name}`` operations. (3.1 embeds JSON Schema 2020-12, so the
  MCP input schemas drop in verbatim. This doc also seeds the local REST gateway
  planned in WP-22.)

**Single source of truth.** Every schema is *derived* from the live FastMCP
registry (``mta.server``) — the very same definitions the server serves over
stdio — so the exports can never drift from the real tools. Nothing here is
hand-maintained.

**Invariant-safe.** Building schemas is pure and offline: it enumerates the
in-process tool registry and returns plain dicts. No network, no model, no
document contents — and these are developer/integrator artifacts (CLI + Python
API), never returned to the model, so the token-free guarantee is untouched.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

__all__ = [
    "export",
    "to_openai",
    "to_gemini",
    "to_openapi",
    "tool_catalogue",
    "write_files",
]

# ---------------------------------------------------------------------------
# Source of truth: the live FastMCP tool registry.
# ---------------------------------------------------------------------------


def _raw_tools() -> list[tuple[str, str, dict]]:
    """Return ``(name, description, input_schema)`` for every registered tool.

    Prefers the public async ``FastMCP.list_tools()`` (protocol ``Tool`` objects
    carrying ``inputSchema``); falls back to the synchronous tool manager when
    called from inside a running event loop.
    """
    import asyncio

    from mta.server import mcp  # registers all eight tools at import time

    try:
        tools = asyncio.run(mcp.list_tools())
    except RuntimeError:
        # Already inside an event loop — read the registry synchronously.
        mgr = getattr(mcp, "_tool_manager", None)
        raw = mgr.list_tools() if mgr is not None else []
        return [
            (t.name, getattr(t, "description", "") or "", getattr(t, "parameters", None) or {})
            for t in raw
        ]
    return [(t.name, t.description or "", t.inputSchema or {}) for t in tools]


def tool_catalogue() -> list[dict]:
    """The normalised, deterministically-ordered tool catalogue.

    Each entry is ``{"name", "description", "input_schema"}``. Sorted by name so
    exported files are stable across runs (clean diffs, reproducible artifacts).
    """
    out = [
        {
            "name": name,
            "description": (desc or "").strip(),
            "input_schema": schema or {"type": "object", "properties": {}},
        }
        for name, desc, schema in _raw_tools()
    ]
    out.sort(key=lambda t: t["name"])
    return out


# ---------------------------------------------------------------------------
# Schema helpers (pure; never mutate the source schema).
# ---------------------------------------------------------------------------


def _strip_titles(node: Any) -> Any:
    """Deep-copy ``node`` dropping pydantic's cosmetic ``title`` keys."""
    if isinstance(node, dict):
        return {k: _strip_titles(v) for k, v in node.items() if k != "title"}
    if isinstance(node, list):
        return [_strip_titles(v) for v in node]
    return node


def _object_schema(schema: dict) -> dict:
    """A clean JSON-Schema object (titles stripped, ``type``/``properties`` set).

    Used for OpenAI ``parameters`` and OpenAPI request bodies — both accept full
    JSON Schema, so nullable unions (``anyOf`` with ``null``) are left intact.
    """
    s = _strip_titles(schema)
    if not isinstance(s, dict):
        s = {}
    s.setdefault("type", "object")
    s.setdefault("properties", {})
    s.pop("$schema", None)
    return s


# Keywords Gemini's schema subset does not accept (or ignores) — drop them.
_GEMINI_DROP = {
    "title",
    "$schema",
    "additionalProperties",
    "default",
    "examples",
    "$defs",
    "definitions",
    "$ref",
    "discriminator",
}


def _gemini_schema(node: Any) -> Any:
    """Normalise a JSON Schema into Gemini's OpenAPI-3.0 subset.

    Collapses ``anyOf``/``oneOf`` nullable unions into a single typed schema with
    ``nullable: true`` and strips JSON-Schema-only keywords Gemini rejects.
    """
    if isinstance(node, list):
        return [_gemini_schema(v) for v in node]
    if not isinstance(node, dict):
        return node

    work = dict(node)

    # Collapse a nullable union (e.g. ``str | None``) into one typed schema.
    for combiner in ("anyOf", "oneOf"):
        if combiner in work:
            variants = work.pop(combiner) or []
            non_null = [
                v for v in variants
                if not (isinstance(v, dict) and v.get("type") == "null")
            ]
            had_null = any(
                isinstance(v, dict) and v.get("type") == "null" for v in variants
            )
            base = dict(non_null[0]) if non_null else {"type": "string"}
            # Carry sibling keys (description, etc.) onto the chosen variant.
            for k, v in work.items():
                base.setdefault(k, v)
            if had_null:
                base["nullable"] = True
            work = base
            break

    out: dict = {}
    for k, v in work.items():
        if k in _GEMINI_DROP:
            continue
        out[k] = _gemini_schema(v)
    return out


# ---------------------------------------------------------------------------
# Format builders.
# ---------------------------------------------------------------------------


def to_openai(catalogue: list[dict] | None = None) -> list[dict]:
    """OpenAI *tools* array: ``[{"type": "function", "function": {...}}, ...]``."""
    cat = catalogue or tool_catalogue()
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": _object_schema(t["input_schema"]),
            },
        }
        for t in cat
    ]


def to_gemini(catalogue: list[dict] | None = None) -> dict:
    """Gemini ``{"function_declarations": [...]}``.

    No-argument tools omit ``parameters`` entirely (Gemini rejects an empty
    object schema), per the function-calling spec.
    """
    cat = catalogue or tool_catalogue()
    decls = []
    for t in cat:
        params = _gemini_schema(t["input_schema"])
        decl = {"name": t["name"], "description": t["description"]}
        if isinstance(params, dict) and params.get("properties"):
            decl["parameters"] = params
        decls.append(decl)
    return {"function_declarations": decls}


def to_openapi(
    catalogue: list[dict] | None = None,
    *,
    title: str = "Memorised them All — local memory tools",
    version: str | None = None,
) -> dict:
    """A self-contained OpenAPI 3.1 document (``POST /tools/{name}`` per tool)."""
    cat = catalogue or tool_catalogue()
    if version is None:
        import mta

        version = mta.__version__

    paths: dict = {}
    for t in cat:
        name = t["name"]
        desc = t["description"]
        summary = desc.splitlines()[0].strip() if desc else name
        schema = _object_schema(t["input_schema"])
        paths[f"/tools/{name}"] = {
            "post": {
                "operationId": name,
                "summary": summary,
                "description": desc,
                "tags": ["memory"],
                "x-mcp-tool": name,
                "requestBody": {
                    "required": bool(schema.get("required")),
                    "content": {"application/json": {"schema": schema}},
                },
                "responses": {
                    "200": {
                        "description": (
                            "Token-free result: compact metadata or a small, relevant "
                            "slice of memory — never document contents."
                        ),
                        "content": {"application/json": {"schema": {"type": "object"}}},
                    }
                },
            }
        }

    return {
        "openapi": "3.1.0",
        "jsonSchemaDialect": "https://json-schema.org/draft/2020-12/schema",
        "info": {
            "title": title,
            "version": version,
            "description": (
                "Local, token-free file → knowledge-graph memory. Eight tools, served "
                "over MCP (stdio) and described here for non-MCP / HTTP clients. All "
                "processing is on-device; nothing is sent to third parties."
            ),
            "license": {"name": "MIT"},
        },
        "tags": [{"name": "memory", "description": "Local digestion & recall tools"}],
        "paths": paths,
    }


_BUILDERS = {
    "openai": to_openai,
    "gemini": to_gemini,
    "openapi": to_openapi,
}


def export(fmt: str = "all", *, catalogue: list[dict] | None = None):
    """Build one format (``openai``/``gemini``/``openapi``) or ``all`` of them.

    ``all`` returns ``{"openai": ..., "gemini": ..., "openapi": ...}``.
    """
    cat = catalogue or tool_catalogue()
    if fmt == "all":
        return {name: build(cat) for name, build in _BUILDERS.items()}
    if fmt not in _BUILDERS:
        raise ValueError(
            f"unknown schema format {fmt!r}; choose from {sorted(_BUILDERS)} or 'all'"
        )
    return _BUILDERS[fmt](cat)


def write_files(data, outdir, fmt: str = "all") -> list[Path]:
    """Write exported schema(s) as ``<format>.json`` under ``outdir``."""
    outdir = Path(outdir).expanduser()
    outdir.mkdir(parents=True, exist_ok=True)
    items = data.items() if fmt == "all" else [(fmt, data)]
    written = []
    for name, obj in items:
        fp = outdir / f"{name}.json"
        fp.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        written.append(fp)
    return written
