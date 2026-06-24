"""Theme-Z — WP-123b: best-effort provenance codepoint-offset spans.

Each locatable fact gains `span:{doc,start,end}` — exact codepoint offsets into the
digest-time `.md` — plus a per-document `md_sha` fingerprint on `documents[]`. Additive,
deterministic, honest best-effort (no span when the stored text can't be found verbatim).
Offline, model-free.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

os.environ.setdefault("MTA_AUTO_UPDATE", "off")


def _cfg(home, project="sp"):
    from mta.core.config import Config
    return Config(home=Path(home)).with_project(project)


def _digest(cfg, text: str):
    from mta.core.digest import digest
    d = Path(cfg.home).parent / "src"
    d.mkdir(parents=True, exist_ok=True)
    (d / "doc.txt").write_text(text, encoding="utf-8")
    return digest(cfg, [str(d)], reset=True)


def _graph(cfg):
    return json.loads(cfg.graph_path.read_text(encoding="utf-8"))


_CORPUS = (
    "Helios Corporation operates the Nevada Power Grid across the desert region.\n"
    "Director Mira Chen approved the Aurora expansion programme.\n"
)


# ---- the normalization/offset helper (no I/O) ----------------------------------------
def test_normalize_with_map_roundtrips_to_original_offsets():
    from mta.core.digest import _normalize_with_map
    src = "Helios   Corporation\noperates"
    norm, pos = _normalize_with_map(src)
    assert norm == "helios corporation operates"
    at = norm.find("corporation")
    start, end = pos[at], pos[at + len("corporation") - 1] + 1
    assert src[start:end] == "Corporation"   # maps back to the exact original slice


# ---- end-to-end through digest -------------------------------------------------------
def test_located_fact_span_points_at_the_md(tmp_path):
    from mta.core.digest import _normalize_with_map
    cfg = _cfg(tmp_path / "h")
    _digest(cfg, _CORPUS)
    g = _graph(cfg)
    spanned = [f for n in g["nodes"] for f in n.get("facts", []) if "span" in f]
    assert spanned, "expected at least one located fact span"
    for f in spanned:
        sp = f["span"]
        md = (cfg.markdown_dir / (sp["doc"] + ".md")).read_text(encoding="utf-8", errors="replace")
        assert 0 <= sp["start"] < sp["end"] <= len(md)
        region = md[sp["start"]:sp["end"]]
        # the .md slice at the span, normalised, IS the fact's normalised text
        assert _normalize_with_map(region)[0] == _normalize_with_map(f["text"])[0]


def test_documents_carry_md_sha_fingerprint(tmp_path):
    cfg = _cfg(tmp_path / "h")
    _digest(cfg, _CORPUS)
    docs = [d for d in _graph(cfg)["documents"] if d.get("status") == "ok"]
    assert docs
    for d in docs:
        assert re.fullmatch(r"[0-9a-f]{12}", d.get("md_sha", "")), d


def test_spans_are_deterministic(tmp_path):
    a = _cfg(tmp_path / "a", "p"); b = _cfg(tmp_path / "b", "p")
    _digest(a, _CORPUS); _digest(b, _CORPUS)
    assert a.graph_path.read_text(encoding="utf-8") == b.graph_path.read_text(encoding="utf-8")
    assert any("span" in f for n in _graph(a)["nodes"] for f in n.get("facts", []))


def test_spans_do_not_leak_into_recall(tmp_path):
    """Spans ride graph.json only — the recall meta + bm25 index (which feed recall) must not
    contain them, so recall stays byte-identical / token-free."""
    from mta.core.store import load_meta, load_bm25_index
    cfg = _cfg(tmp_path / "h")
    _digest(cfg, _CORPUS)
    assert '"span"' not in json.dumps(load_meta(cfg), ensure_ascii=False)
    assert '"span"' not in json.dumps(load_bm25_index(cfg), ensure_ascii=False)


def test_unlocatable_fact_simply_has_no_span(tmp_path):
    """A fact whose stored text isn't verbatim in the .md (here: PII-redacted digits) gets no
    span rather than a wrong one — honest best-effort."""
    cfg = _cfg(tmp_path / "h")
    # a redacted long digit-run becomes "[number]" in the fact but is digits in the .md
    _digest(cfg, "Contact the Helios Corporation desk on 01711 234567 about the Grid.\n")
    facts = [f for n in _graph(cfg)["nodes"] for f in n.get("facts", [])]
    for f in facts:
        if "[number]" in f.get("text", ""):
            assert "span" not in f          # can't be located verbatim → no span
