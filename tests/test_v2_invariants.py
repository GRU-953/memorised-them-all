"""WP-80 — v2.0.0 invariants: fully deterministic, fully model-free, exactly 8 tools.

These are the contract tests for the v2 re-architecture. If any of these fail, the
release promise ("no models, no network, byte-identical output") is broken.
"""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

os.environ.setdefault("MTA_AUTO_UPDATE", "off")

REPO = Path(__file__).resolve().parents[1]
SAMPLE = REPO / "sample"


def _cfg(home, project="inv"):
    from mta.core.config import Config
    return Config(home=Path(home)).with_project(project)


# ---- model-free: the model modules are GONE, not just unused ------------------------
def test_model_modules_are_gone():
    assert importlib.util.find_spec("mta.core.backends") is None
    assert importlib.util.find_spec("mta.core.lifecycle") is None


def test_no_module_references_ollama():
    # Scan for actual CODE constructs (imports, classes, API endpoints) — docstring
    # prose explaining that v2 has "no Ollama" is fine and expected.
    import re

    import mta
    pkg_root = Path(mta.__file__).parent
    needles = re.compile(
        r"OllamaManager|from \.(?:lifecycle|backends)|from mta\.core\.(?:lifecycle|backends)"
        r"|import ollama|ollama_host|OLLAMA_HOST|/api/generate|/api/embeddings|/api/tags")
    offenders = []
    for py in pkg_root.rglob("*.py"):
        for i, line in enumerate(py.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if needles.search(line):
                offenders.append(f"{py.name}:{i}: {line.strip()}")
    assert not offenders, offenders


# ---- exactly 8 tools; open_mindmap absent --------------------------------------------
def test_exactly_eight_tools():
    from mta import server
    srv = server.build_server()
    import anyio

    async def _names():
        return {t.name for t in await srv.list_tools()}

    names = anyio.run(_names)
    assert names == {"digest", "convert", "recall", "memory_overview", "export_memory",
                     "list_digestible", "forget", "memory_status"}, names


# ---- determinism: byte-identical artifacts across runs -------------------------------
def test_graph_and_vectors_are_byte_identical_across_runs(tmp_path):
    from mta.core.digest import digest
    outs = []
    for run in ("a", "b"):
        cfg = _cfg(tmp_path / run)
        d = digest(cfg, [str(SAMPLE)])
        assert d["status"] == "ok"
        # NO normalisation: the v2 contract is byte-identical persisted artifacts.
        outs.append((cfg.graph_path.read_text(encoding="utf-8"),
                     cfg.vectors_path.read_bytes() if cfg.vectors_path.exists() else b"",
                     cfg.memory_md.read_text(encoding="utf-8"),
                     cfg.bm25_index_path.read_bytes() if cfg.bm25_index_path.exists() else b""))
    assert outs[0][0] == outs[1][0], "graph.json differs between identical runs"
    assert outs[0][1] == outs[1][1], "vectors.npz differs between identical runs"
    assert outs[0][2] == outs[1][2], "memory.md differs between identical runs"
    assert outs[0][3] == outs[1][3], "bm25_index.json differs between identical runs"


# ---- zero network: a digest must never open a socket ---------------------------------
def test_digest_makes_no_network_calls(tmp_path, monkeypatch):
    import socket

    def _no_net(*a, **k):
        raise AssertionError("network access attempted during a digest")

    monkeypatch.setattr(socket, "socket", _no_net)
    monkeypatch.setattr(socket, "create_connection", _no_net)
    from mta.core.digest import digest
    cfg = _cfg(tmp_path)
    cfg.convert_timeout = 0          # in-process conversion (a spawn pool uses sockets internally)
    cfg.workers = 1
    d = digest(cfg, [str(SAMPLE / "aurora-project.md")])
    assert d["status"] == "ok" and d["stats"]["entities"] >= 1
