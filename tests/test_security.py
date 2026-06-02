"""WP-32 — security hardening (SEC-01 bomb cap on all containers · SEC-03 pickle ·
SEC-10 zero-network mind map). Offline; runs on the standard CI matrix."""
from __future__ import annotations

import os
import zipfile
from pathlib import Path

import numpy as np

os.environ.setdefault("MTA_NO_OLLAMA", "1")
os.environ.setdefault("MTA_AUTO_UPDATE", "off")
os.environ.setdefault("MTA_EXTRACT", "classical")

REPO = Path(__file__).resolve().parents[1]
SAMPLE = REPO / "sample"


def _cfg(tmp_path, project="sec"):
    os.environ["MTA_HOME"] = str(tmp_path)
    from mta.core.config import load
    return load().with_project(project)


def test_bomb_docx_is_skipped(tmp_path):
    """SEC-01: a zip-bomb disguised as .docx is rejected (only literal .zip was checked)."""
    z = tmp_path / "bomb.docx"
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("word/document.xml", "a" * (8 * 1024 * 1024))  # ~8 MB → ~KB compressed
    from mta.core.convert import convert_file
    r = convert_file(z, tmp_path / "out", _cfg(tmp_path))
    assert r.status == "skipped" and r.method == "zip-too-large", (r.status, r.method)


def test_nested_archive_in_xlsx_rejected(tmp_path):
    """SEC-01: the nested-archive recursive-bomb vector is caught for OOXML too."""
    z = tmp_path / "x.xlsx"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("inner.zip", b"PK\x03\x04 nested archive")
    from mta.core.convert import convert_file
    r = convert_file(z, tmp_path / "out", _cfg(tmp_path))
    assert r.status == "skipped" and r.method == "zip-too-large", (r.status, r.method)


def test_vector_store_rejects_pickle(tmp_path):
    """SEC-03: a pickled object array in vectors.npz is refused, not executed."""
    cfg = _cfg(tmp_path, "pk")
    cfg.ensure_dirs()
    np.savez(str(cfg.vectors_path), matrix=np.array([{"x": 1}], dtype=object))
    cfg.vectors_path.with_suffix(".json").write_text("[]", encoding="utf-8")
    from mta.core.store import load_vectors
    assert load_vectors(cfg) is None        # allow_pickle=False → refused → None


def test_mindmap_is_zero_network(tmp_path):
    """SEC-10: the mind map inlines Cytoscape and loads NOTHING from the network."""
    cfg = _cfg(tmp_path, "mm")
    from mta.core.digest import digest
    digest(cfg, [str(SAMPLE)])
    html = cfg.mindmap_html.read_text(encoding="utf-8")
    assert "cytoscape" in html.lower()      # the library is present (inlined)
    assert "unpkg" not in html              # no CDN fallback
    assert "<script src=" not in html       # no external script tags at all


def test_summary_prompt_is_fenced(monkeypatch):
    """SEC-02: the theme summariser fences document-derived text as data."""
    from mta.core import digest
    from mta.core.config import load
    monkeypatch.delenv("MTA_EXTRACT", raising=False)
    captured = {}
    monkeypatch.setattr(digest, "_llm_summarise",
                        lambda prompt, cfg, ollama: captured.setdefault("p", prompt) or "ok")
    cfg = load()
    cfg.extract_mode = "auto"   # force the LLM-summary branch
    digest._community_summary(["Helios operates in Reykjavik."], ["Helios"], cfg, ollama=None)
    assert "<<<DATA>>>" in captured["p"] and "<<<END>>>" in captured["p"]
