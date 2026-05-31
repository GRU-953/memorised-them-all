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
    chunks = segment_markdown((SAMPLE / "aurora-project.md").read_text(encoding="utf-8"),
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
    graph_doc = json.loads(cfg.graph_path.read_text(encoding="utf-8"))
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
    html = cfg.mindmap_html.read_text(encoding="utf-8")
    assert "cytoscape" in html.lower()


def test_accumulation_and_reset(tmp_path):
    """Digesting a second set extends the same project; reset wipes it."""
    import json
    cfg = _fresh_cfg(tmp_path, "acc")
    from mta.core.digest import digest
    digest(cfg, [str(SAMPLE / "aurora-project.md")])
    digest(cfg, [str(SAMPLE / "notes.txt")])           # should ACCUMULATE
    docs = {d["name"] for d in json.loads(cfg.graph_path.read_text(encoding="utf-8"))["documents"]
            if d["status"] == "ok"}
    assert {"aurora-project.md", "notes.txt"} <= docs, docs

    digest(cfg, [str(SAMPLE / "aurora-project.md")], reset=True)  # should WIPE
    docs2 = {d["name"] for d in json.loads(cfg.graph_path.read_text(encoding="utf-8"))["documents"]
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
    assert "Helios" in (tmp_path / "out" / "note.png.md").read_text(encoding="utf-8")


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
    (corpus / "real.md").write_text((SAMPLE / "aurora-project.md").read_text(encoding="utf-8"))
    (corpus / "junk.txt").write_text(("spam " * 3000 + "\n") * 20, encoding="utf-8")
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


def test_fast_mode_is_deterministic(tmp_path):
    """Fast mode (no LLM) yields a byte-stable graph across runs (same content)."""
    import json

    def sig(cfg):
        gd = json.loads(cfg.graph_path.read_text(encoding="utf-8"))
        return (sorted((n["label"], n["type"]) for n in gd["nodes"]),
                sorted((e["source"], e["target"], e["weight"]) for e in gd["edges"]),
                [sorted(c["members"]) for c in gd["communities"]])

    from mta.core.digest import digest
    c1 = _fresh_cfg(tmp_path / "a", "f")
    digest(c1, [str(SAMPLE)], fast=True)
    c2 = _fresh_cfg(tmp_path / "b", "f")
    digest(c2, [str(SAMPLE)], fast=True)
    assert sig(c1) == sig(c2)
    assert json.loads(c1.graph_path.read_text(encoding="utf-8"))["stats"]["mode"] == "fast"


def test_fact_attribution_word_boundary_and_no_dup():
    """Facts attach by word boundary (no 'Cat' in 'Category') and never duplicate."""
    from mta.core.extract import Extraction
    from mta.core.graph import build_graph
    from mta.core.segment import Chunk

    canonical = {"e0": {"label": "Cat", "type": "other", "aliases": [], "count": 2},
                 "e1": {"label": "Dog", "type": "other", "aliases": [], "count": 1},
                 "e2": {"label": "Acme Inc.", "type": "org", "aliases": [], "count": 1}}
    alias_to_cid = {"cat": "e0", "dog": "e1", "acme inc": "e2"}
    ch = Chunk(id="d#0", doc="d", heading_path="d", index=0,
               text="The Category includes a Dog. Acme Inc. shipped it.")
    # Same canonical entity referenced via two surface forms in one chunk.
    ex = Extraction(entities=[{"name": "Cat", "type": "other"},
                              {"name": "cat", "type": "other"},
                              {"name": "Dog", "type": "other"},
                              {"name": "Acme Inc.", "type": "org"}],
                    relations=[], facts=["The Category includes a Dog.",
                                         "Acme Inc. shipped it."])
    g = build_graph([(ch, ex)], alias_to_cid, canonical)
    assert len(g.nodes["e0"]["facts"]) == 0           # "Cat" not matched in "Category"
    assert len(g.nodes["e1"]["facts"]) == 1           # "Dog" matched once, not twice
    # Label ending in punctuation still attaches (lookaround boundary, not \b).
    assert any("Acme Inc." in f["text"] for f in g.nodes["e2"]["facts"])


def test_acronym_links_to_expansion():
    """'NGA' resolves to 'Nordic Grid Authority' (acronym ↔ expansion)."""
    import numpy as np
    from mta.core.resolve import cid_for, resolve_entities

    class _Ortho:  # orthogonal embeddings → no embedding-based merge
        def embed(self, names):
            return np.eye(len(names), dtype=np.float32)

    mentions = ([{"name": "Nordic Grid Authority", "type": "org"}] * 2
                + [{"name": "NGA", "type": "org"}])
    res = resolve_entities(mentions, _Ortho())
    a2c = res["alias_to_cid"]
    assert cid_for("NGA", a2c) == cid_for("Nordic Grid Authority", a2c)
    assert res["canonical"][cid_for("NGA", a2c)]["label"] == "Nordic Grid Authority"


def test_zip_bomb_is_skipped(tmp_path):
    """A high-ratio archive is skipped before MarkItDown extracts it."""
    import zipfile
    z = tmp_path / "bomb.zip"
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("big.txt", "a" * (8 * 1024 * 1024))  # compresses to ~KB
    cfg = _fresh_cfg(tmp_path, "zip")
    from mta.core.convert import convert_file
    r = convert_file(z, tmp_path / "out", cfg)
    assert r.status == "skipped" and r.method == "zip-too-large", (r.status, r.method)


def test_convert_worker_accepts_payload(tmp_path):
    """The process-pool worker accepts the 4-tuple payload (guards against a
    regression where a stray unpack silently disabled conversion parallelism)."""
    import os
    os.environ["MTA_HOME"] = str(tmp_path)
    from mta.core.config import load
    from mta.core.digest import _convert_worker
    src = tmp_path / "x.txt"
    src.write_text("Helios Energy operates in Reykjavik.", encoding="utf-8")
    r = _convert_worker((str(src), str(tmp_path / "out"), load(), "x.txt.md"))
    assert r["status"] == "ok"
    assert r["output"].endswith("x.txt.md")


def test_nested_archive_rejected(tmp_path):
    """An archive containing a nested archive is rejected (recursive-bomb vector)."""
    import io
    import zipfile
    inner = io.BytesIO()
    with zipfile.ZipFile(inner, "w") as iz:
        iz.writestr("inner.txt", "hello")
    outer = tmp_path / "outer.zip"
    with zipfile.ZipFile(outer, "w") as oz:
        oz.writestr("nested.zip", inner.getvalue())
    cfg = _fresh_cfg(tmp_path, "nz")
    from mta.core.convert import convert_file
    r = convert_file(outer, tmp_path / "out", cfg)
    assert r.status == "skipped" and r.method == "zip-too-large", (r.status, r.method)


def test_oversize_file_is_skipped(tmp_path):
    """Files over the size cap are skipped before being read into memory."""
    big = tmp_path / "big.txt"
    big.write_text("x" * (2 * 1024 * 1024), encoding="utf-8")  # 2 MB
    cfg = _fresh_cfg(tmp_path, "sz")
    cfg.max_file_mb = 1  # cap at 1 MB
    from mta.core.convert import convert_file
    r = convert_file(big, tmp_path / "out", cfg)
    assert r.status == "skipped" and r.method == "too-large", (r.status, r.method)


def test_acronym_no_false_merge():
    """An ambiguous acronym (two expansions share initials) links to neither."""
    import numpy as np
    from mta.core.resolve import cid_for, resolve_entities

    class _Ortho:
        def embed(self, names):
            return np.eye(len(names), dtype=np.float32)

    mentions = [{"name": "World Health Organization", "type": "org"},
                {"name": "World Heritage Organisation", "type": "org"},
                {"name": "WHO", "type": "org"}]
    res = resolve_entities(mentions, _Ortho())
    a2c = res["alias_to_cid"]
    assert cid_for("World Health Organization", a2c) != cid_for("World Heritage Organisation", a2c)


def test_recall_hit_is_bounded():
    """Each recall hit clamps text length and docs count (token-free guarantee)."""
    from mta.core.recall import _hit
    u = {"kind": "theme", "label": "X", "text": "y" * 5000,
         "docs": [f"d{i}" for i in range(30)]}
    h = _hit(u, 0.5)
    assert len(h["text"]) <= 600
    assert len(h["docs"]) <= 5
    assert h["doc_count"] == 30


def test_same_basename_no_data_loss(tmp_path):
    """Two same-named files in different folders both survive (no silent overwrite)."""
    corpus = tmp_path / "c"
    (corpus / "a").mkdir(parents=True)
    (corpus / "b").mkdir(parents=True)
    (corpus / "a" / "notes.txt").write_text("Alpha mentions Helios Energy in Reykjavik.",
                                            encoding="utf-8")
    (corpus / "b" / "notes.txt").write_text("Beta mentions Vptr Robotics in Oslo.",
                                            encoding="utf-8")
    cfg = _fresh_cfg(tmp_path, "col")
    from mta.core.digest import digest
    res = digest(cfg, [str(corpus)])
    assert res["stats"]["converted"] == 2, res["stats"]
    assert len(list(cfg.markdown_dir.glob("*.md"))) == 2


def test_forget_deletes_project(tmp_path):
    from mta.core.digest import digest
    from mta.core.store import delete_project
    cfg = _fresh_cfg(tmp_path, "gone")
    digest(cfg, [str(SAMPLE)])
    assert cfg.project_dir.exists()
    r = delete_project(cfg)
    assert r["status"] == "ok" and not cfg.project_dir.exists()


def test_idle_shutdown_only_stops_ours(tmp_path):
    # With Ollama disabled, ensure_running is False and nothing is started/stopped.
    os.environ["MTA_HOME"] = str(tmp_path)
    from mta.core.config import load
    from mta.core.lifecycle import OllamaManager
    m = OllamaManager(load())
    assert m.ensure_running(wait=1) is False
    m.stop()  # no-op, must not raise
