"""WP-21 — cross-AI tool-schema exports (OpenAI / Gemini / OpenAPI 3.1).

Fully offline: builds schemas from the in-process FastMCP registry and asserts
shape + the no-drift guarantee + the Gemini-subset cleanliness rules. No network,
no Ollama, no converters.
"""
from __future__ import annotations

import json
import os

os.environ.setdefault("MTA_NO_OLLAMA", "1")
os.environ.setdefault("MTA_AUTO_UPDATE", "off")

import pytest

from mta.interop import schemas

EXPECTED = {
    "digest", "convert", "recall", "memory_overview", "export_memory",
    "list_digestible", "forget", "memory_status", "open_mindmap",
}


def _keys_absent(node, key: str) -> bool:
    """True iff `key` appears nowhere in the nested structure."""
    if isinstance(node, dict):
        if key in node:
            return False
        return all(_keys_absent(v, key) for v in node.values())
    if isinstance(node, list):
        return all(_keys_absent(v, key) for v in node)
    return True


# ---- catalogue (the single source of truth) --------------------------------

def test_catalogue_matches_the_eight_mcp_tools():
    cat = schemas.tool_catalogue()
    assert {t["name"] for t in cat} == EXPECTED
    # deterministic ordering (stable exported files)
    assert [t["name"] for t in cat] == sorted(t["name"] for t in cat)
    for t in cat:
        assert t["description"].strip()                 # real docstring, not empty
        assert t["input_schema"].get("type") == "object"


def test_catalogue_does_not_drift_from_the_live_server():
    """The exported names/descriptions are exactly what the server registers."""
    import asyncio

    from mta.server import mcp
    live = {t.name: (t.description or "").strip() for t in asyncio.run(mcp.list_tools())}
    cat = {t["name"]: t["description"] for t in schemas.tool_catalogue()}
    assert cat == live


# ---- OpenAI ----------------------------------------------------------------

def test_openai_tools_array_shape():
    tools = schemas.to_openai()
    assert {t["function"]["name"] for t in tools} == EXPECTED
    for t in tools:
        assert t["type"] == "function"
        fn = t["function"]
        assert fn["description"].strip()
        params = fn["parameters"]
        assert params["type"] == "object" and "properties" in params
        assert _keys_absent(params, "title")            # pydantic noise stripped
        assert _keys_absent(params, "$schema")
    json.dumps(tools)                                    # must be JSON-serialisable


# ---- Gemini ----------------------------------------------------------------

def test_gemini_function_declarations_are_subset_clean():
    g = schemas.to_gemini()
    decls = g["function_declarations"]
    assert {d["name"] for d in decls} == EXPECTED
    for d in decls:
        assert d["description"].strip()
        params = d.get("parameters")
        if params is not None:
            assert params["type"] == "object" and params.get("properties")
            # keys Gemini's OpenAPI-3.0 subset rejects must be gone everywhere
            for banned in ("$schema", "additionalProperties", "title", "default",
                           "anyOf", "oneOf", "$ref"):
                assert _keys_absent(params, banned), banned
    json.dumps(g)


def test_gemini_omits_parameters_for_no_arg_tools():
    decls = {d["name"]: d for d in schemas.to_gemini()["function_declarations"]}
    # memory_status takes no arguments → Gemini wants no `parameters` key at all
    assert "parameters" not in decls["memory_status"]
    # digest has required args → parameters present with a non-empty schema
    assert decls["digest"]["parameters"]["properties"]


# ---- OpenAPI 3.1 -----------------------------------------------------------

def test_openapi_31_document_structure():
    import mta

    doc = schemas.to_openapi()
    assert doc["openapi"] == "3.1.0"
    assert doc["info"]["version"] == mta.__version__       # tracks the package version
    paths = doc["paths"]
    for name in EXPECTED:
        op = paths[f"/tools/{name}"]["post"]
        assert op["operationId"] == name
        assert op["x-mcp-tool"] == name
        sch = op["requestBody"]["content"]["application/json"]["schema"]
        assert sch["type"] == "object"
        assert "200" in op["responses"]
    json.dumps(doc)


# ---- dispatcher + file writer ----------------------------------------------

def test_export_dispatch_and_unknown_format():
    everything = schemas.export("all")
    assert set(everything) == {"openai", "gemini", "openapi"}
    assert schemas.export("openai") == everything["openai"]
    with pytest.raises(ValueError):
        schemas.export("yaml")


def test_write_files_emits_named_json(tmp_path):
    written = schemas.write_files(schemas.export("all"), tmp_path, "all")
    names = {p.name for p in written}
    assert names == {"openai.json", "gemini.json", "openapi.json"}
    for p in written:
        json.loads(p.read_text(encoding="utf-8"))         # each file is valid JSON


# ---- CLI -------------------------------------------------------------------

def test_cli_export_schema_stdout(capsys):
    from mta.cli import main
    rc = main(["export-schema", "--format", "openapi"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["openapi"] == "3.1.0"


def test_cli_export_schema_writes_files(tmp_path, capsys):
    from mta.cli import main
    rc = main(["export-schema", "--format", "all", "--out", str(tmp_path)])
    assert rc == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "ok"
    assert (tmp_path / "openai.json").exists()
    assert (tmp_path / "gemini.json").exists()
    assert (tmp_path / "openapi.json").exists()
