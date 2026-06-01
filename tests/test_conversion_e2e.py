"""Real-conversion end-to-end tests.

These exercise the ACTUAL MarkItDown converters (PDF / DOCX / XLSX / CSV / HTML) —
the code path the offline smoke lane skips, because that lane installs no
converters (`pip install -e . --no-deps`). Gated on `markitdown` being importable,
so the module SKIPS on the offline lane and RUNS on the full-deps CI lane (and
locally when the converters are installed).

Still fully offline (``MTA_NO_OLLAMA=1`` → classical extraction + hashing
embeddings), so no models or network are needed.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("MTA_NO_OLLAMA", "1")
os.environ.setdefault("MTA_AUTO_UPDATE", "off")
os.environ.setdefault("MTA_EXTRACT", "classical")

pytest.importorskip("markitdown", reason="conversion deps not installed (offline lane)")

FIXTURES = Path(__file__).resolve().parent / "fixtures"
DOC_FORMATS = ["report.pdf", "memo.docx", "data.xlsx", "table.csv", "page.html"]


def _cfg(tmp_path, project="conv"):
    os.environ["MTA_HOME"] = str(tmp_path)
    from mta.core.config import load
    return load().with_project(project)


def test_real_document_conversion_e2e(tmp_path):
    """A folder of real PDF/DOCX/XLSX/CSV/HTML digests via the actual converters."""
    cfg = _cfg(tmp_path)
    from mta.core.digest import digest
    res = digest(cfg, [str(FIXTURES)])
    assert res["status"] == "ok", res
    s = res["stats"]
    assert s["files"] >= len(DOC_FORMATS), s
    assert s["converted"] >= len(DOC_FORMATS), s          # every document converted
    assert s["chunks"] > 0, s

    # Token-free contract: no raw fixture text leaks into the tool result.
    assert "Lena Marsh" not in json.dumps(res)

    # Entities from the converted documents reached the graph.
    gd = json.loads(cfg.graph_path.read_text(encoding="utf-8"))
    labels = " ".join(n["label"] for n in gd["nodes"])
    assert any(t in labels for t in ("Aurora", "Helios", "Reykjavik", "Marsh", "Vptr")), labels

    # Recall works over the converted content and stays a small slice.
    from mta.core.recall import recall
    out = recall(cfg, "Who leads Project Aurora?", k=5)
    assert out["status"] == "ok"
    assert len(out["hits"]) <= 5


def test_each_document_format_converts(tmp_path):
    """Each format converts on its own (isolates a per-converter regression)."""
    from mta.core.convert import convert_file
    cfg = _cfg(tmp_path, "fmt")
    outdir = tmp_path / "out"
    for name in DOC_FORMATS:
        src = FIXTURES / name
        assert src.exists(), f"missing committed fixture: {name}"
        r = convert_file(src, outdir, cfg)
        assert r.status == "ok", (name, r.status, getattr(r, "method", None))
