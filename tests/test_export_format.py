"""Cycle-4: the export bundle conforms to docs/export-format/v1 (schema + referential integrity).

Dependency-free by default: a purpose-built validator enforces the documented contract
(required keys, types, stable-ID referential integrity). If `jsonschema` happens to be
importable it ALSO runs full JSON-Schema validation — but we never add it as a dependency.
The digested+exported bundle is the "sample-ingestion fixture" for cross-AI consumption.
Offline.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

os.environ.setdefault("MTA_AUTO_UPDATE", "off")

import pytest

from mta.core.config import Config
from mta.core.digest import digest
from mta.core import render

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "docs" / "export-format" / "v1" / "graph.schema.json"
_ID = re.compile(r"^e[0-9]+$")


def _export(tmp_path) -> Path:
    docs = tmp_path / "docs"; docs.mkdir()
    (docs / "grid.md").write_text(
        "The Nordic Grid Authority (NGA) is based in Oslo. Bjorn Haugen directs it.\n"
        "Helios Energy supplies the Nyx Substation; Dr. Lena Marsh leads Project Aurora.\n",
        encoding="utf-8")
    cfg = Config(home=tmp_path / "h").with_project("exp"); cfg.ensure_dirs()
    assert digest(cfg, [str(docs)], reset=True)["status"] == "ok"
    dest = tmp_path / "bundle"
    render.export_bundle(cfg, str(dest))
    return dest


def _conforms(graph: dict) -> None:
    """The dependency-free contract validator (mirrors graph.schema.json)."""
    for key in ("version", "nodes", "edges", "communities"):
        assert key in graph, f"missing top-level {key}"
    assert isinstance(graph["version"], int) and graph["version"] >= 1
    node_ids = set()
    for n in graph["nodes"]:
        assert _ID.match(n["id"]), f"bad node id {n['id']!r}"
        assert isinstance(n["label"], str) and isinstance(n["type"], str)
        for f in n.get("facts", []):
            assert isinstance(f.get("text"), str)
        node_ids.add(n["id"])
    # referential integrity: edges + community members reference real node IDs
    for e in graph["edges"]:
        assert e["source"] in node_ids and e["target"] in node_ids, "dangling edge"
    for c in graph["communities"]:
        assert isinstance(c["id"], int) and isinstance(c["label"], str)
        for m in c.get("members", []):
            assert m in node_ids, f"community member {m!r} is not a node"


def test_schema_file_is_valid_json():
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert schema["$schema"].startswith("https://json-schema.org/")
    assert "nodes" in schema["properties"] and "edges" in schema["properties"]


def test_exported_graph_conforms_and_is_referentially_intact(tmp_path):
    dest = _export(tmp_path)
    graph = json.loads((dest / "graph.json").read_text(encoding="utf-8"))
    _conforms(graph)
    assert graph["nodes"] and graph["edges"]            # non-trivial graph extracted


def test_markdown_set_is_utf8(tmp_path):
    dest = _export(tmp_path)
    md = dest / "memory.md"
    assert md.exists()
    md.read_text(encoding="utf-8")                       # decodes as UTF-8 (raises otherwise)


def test_full_jsonschema_validation_when_available(tmp_path):
    jsonschema = pytest.importorskip("jsonschema")       # optional; never a hard dependency
    dest = _export(tmp_path)
    graph = json.loads((dest / "graph.json").read_text(encoding="utf-8"))
    jsonschema.validate(graph, json.loads(SCHEMA.read_text(encoding="utf-8")))
