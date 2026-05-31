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


def test_accumulation_and_reset(tmp_path):
    """Digesting a second set extends the same project; reset wipes it."""
    import json
    cfg = _fresh_cfg(tmp_path, "acc")
    from mta.core.digest import digest
    digest(cfg, [str(SAMPLE / "aurora-project.md")])
    digest(cfg, [str(SAMPLE / "notes.txt")])           # should ACCUMULATE
    docs = {d["name"] for d in json.loads(cfg.graph_path.read_text())["documents"]
            if d["status"] == "ok"}
    assert {"aurora-project.md", "notes.txt"} <= docs, docs

    digest(cfg, [str(SAMPLE / "aurora-project.md")], reset=True)  # should WIPE
    docs2 = {d["name"] for d in json.loads(cfg.graph_path.read_text())["documents"]
             if d["status"] == "ok"}
    assert docs2 == {"aurora-project.md"}, docs2


def test_ocr_stdin_pipe(tmp_path):
    """Image OCR uses the stdin pipe and extracts exact text (local only)."""
    import shutil
    if not shutil.which("tesseract"):
        import pytest
        pytest.skip("tesseract not installed")
    PIL = __import__("importlib").import_module("PIL.ImageDraw")  # noqa
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (640, 120), "white")
    ImageDraw.Draw(img).text((20, 40), "Helios Energy Reykjavik report", fill="black")
    p = tmp_path / "note.png"
    img.save(p)
    cfg = _fresh_cfg(tmp_path, "ocr")
    from mta.core.convert import convert_file
    r = convert_file(p, tmp_path / "out", cfg)
    assert r.status == "ok" and r.method == "tesseract", (r.status, r.method)
    assert "Helios" in (tmp_path / "out" / "note.png.md").read_text()


def test_segment_hard_splits_oversize(tmp_path):
    """A long unpunctuated blob is split into chunk-sized windows (no silent loss)."""
    from mta.core.segment import segment_markdown
    blob = "word " * 4000  # ~20k chars, no sentence boundaries
    chunks = segment_markdown(blob, "blob", 1200)
    assert len(chunks) > 10, len(chunks)
    assert all(len(c.text) <= 1400 for c in chunks)


def test_low_value_chunks_skipped(tmp_path):
    """Degenerate repetitive content is skipped, not sent to extraction."""
    import json
    corpus = tmp_path / "c"
    corpus.mkdir()
    (corpus / "real.md").write_text((SAMPLE / "aurora-project.md").read_text())
    (corpus / "junk.txt").write_text(("spam " * 3000 + "\n") * 20)
    cfg = _fresh_cfg(tmp_path, "lv")
    from mta.core.digest import digest
    res = digest(cfg, [str(corpus)])
    s = res["stats"]
    assert s["chunks_skipped_low_value"] > 0, s
    assert s["unique_chunks"] < 30, s          # junk did not flood extraction
    assert s["entities"] >= 3                    # real content still digested


def test_entity_resolution_no_overmerge():
    """Even with maximally-similar embeddings, token-distinct entities stay apart."""
    import numpy as np
    from mta.core.resolve import resolve_entities

    class _StubEmbedder:
        def embed(self, names):
            # Every name embeds to the SAME unit vector → cosine 1.0 everywhere,
            # i.e. the worst case that previously collapsed everything.
            v = np.ones((len(names), 4), dtype=np.float32)
            v /= np.linalg.norm(v, axis=1, keepdims=True)
            return v

    mentions = ([{"name": "Helios Energy", "type": "org"}] * 3
                + [{"name": "Helios", "type": "org"},
                   {"name": "Vptr Robotics", "type": "org"},
                   {"name": "Nordic Grid Authority", "type": "org"},
                   {"name": "Dr. Lena Marsh", "type": "person"},
                   {"name": "Lena Marsh", "type": "person"}])
    res = resolve_entities(mentions, _StubEmbedder())
    labels = {c["label"] for c in res["canonical"].values()}
    # Distinct orgs must NOT have collapsed into a single node.
    assert len(res["canonical"]) >= 4, res["canonical"]
    assert "Vptr Robotics" in labels and "Nordic Grid Authority" in labels, labels
    # But token-overlapping variants SHOULD merge.
    from mta.core.resolve import cid_for
    a2c = res["alias_to_cid"]
    assert cid_for("Helios Energy", a2c) == cid_for("Helios", a2c)
    assert cid_for("Dr. Lena Marsh", a2c) == cid_for("Lena Marsh", a2c)


def test_idle_shutdown_only_stops_ours(tmp_path):
    # With Ollama disabled, ensure_running is False and nothing is started/stopped.
    os.environ["MTA_HOME"] = str(tmp_path)
    from mta.core.config import load
    from mta.core.lifecycle import OllamaManager
    m = OllamaManager(load())
    assert m.ensure_running(wait=1) is False
    m.stop()  # no-op, must not raise
