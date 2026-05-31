"""Offline smoke + end-to-end tests.

Run fully offline (``MTA_NO_OLLAMA=1`` → hashing embeddings + classical
extraction), so they pass in CI on any platform without models. They verify the
whole pipeline produces a graph and memory artefacts, that outputs are
metadata-only (no document text leaks back), and that recall returns a small slice.
"""
from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("MTA_NO_OLLAMA", "1")
os.environ.setdefault("MTA_AUTO_UPDATE", "off")
os.environ.setdefault("MTA_EXTRACT", "classical")

REPO = Path(__file__).resolve().parents[1]
SAMPLE = REPO / "sample"


def _fresh_cfg(tmp_path, project="t"):
    os.environ["MTA_HOME"] = str(tmp_path)
    from mta.core.config import load
    return load().with_project(project)


def test_imports():
    import mta
    from mta.core import (config, convert, digest, embed, extract, graph,
                          lifecycle, platform, recall, render, resolve,
                          segment, store, updater)  # noqa: F401
    assert mta.__version__


def test_segment_and_resolve(tmp_path):
    from mta.core.segment import segment_markdown
    chunks = segment_markdown((SAMPLE / "aurora-project.md").read_text(),
                              "aurora", 400)
    assert len(chunks) >= 2
    assert all(c.heading_path for c in chunks)


def test_digest_end_to_end(tmp_path):
    cfg = _fresh_cfg(tmp_path)
    from mta.core.digest import digest
    res = digest(cfg, [str(SAMPLE)])
    assert res["status"] == "ok", res
    stats = res["stats"]
    assert stats["files"] >= 2
    assert stats["converted"] >= 2
    assert stats["entities"] >= 3, stats
    assert stats["embed_mode"] == "hash"  # offline fallback

    # Artefacts exist.
    assert cfg.graph_path.exists()
    assert cfg.memory_md.exists()
    assert cfg.mindmap_html.exists()
    assert list(cfg.memory_dir.glob("*.md"))

    # The tool result must NOT contain raw document text (token-free contract).
    import json
    blob = json.dumps(res)
    assert "distribution losses by 12 percent" not in blob

    # Key entity made it into the graph.
    graph_doc = json.loads(cfg.graph_path.read_text())
    labels = {n["label"] for n in graph_doc["nodes"]}
    assert any("Aurora" in l or "Helios" in l or "Marsh" in l for l in labels), labels


def test_recall_returns_small_slice(tmp_path):
    cfg = _fresh_cfg(tmp_path)
    from mta.core.digest import digest
    from mta.core.recall import recall
    digest(cfg, [str(SAMPLE)])
    out = recall(cfg, "Who leads Project Aurora?", k=5)
    assert out["status"] == "ok"
    assert len(out["hits"]) <= 5
    # A slice, not whole documents.
    assert all(len(h["text"]) < 1000 for h in out["hits"])


def test_mindmap_is_offline(tmp_path):
    cfg = _fresh_cfg(tmp_path)
    from mta.core.digest import digest
    digest(cfg, [str(SAMPLE)])
    html = cfg.mindmap_html.read_text()
    assert "cytoscape" in html.lower()


def test_idle_shutdown_only_stops_ours(tmp_path):
    # With Ollama disabled, ensure_running is False and nothing is started/stopped.
    os.environ["MTA_HOME"] = str(tmp_path)
    from mta.core.config import load
    from mta.core.lifecycle import OllamaManager
    m = OllamaManager(load())
    assert m.ensure_running(wait=1) is False
    m.stop()  # no-op, must not raise
