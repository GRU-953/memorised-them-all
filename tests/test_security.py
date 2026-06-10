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

