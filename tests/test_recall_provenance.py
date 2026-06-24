"""Theme-Z — WP-134: provenance pointers in recall (the first consumer brick).

Recall now surfaces the WP-123b fact spans as pointer-only `spans` ({doc,start,end}) on
entity hits — computed at query time from `graph.json`, so the stored recall index is
unchanged and old stores still work. Pointer-only → token-free. Offline, model-free.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("MTA_AUTO_UPDATE", "off")


def _cfg(home, project="rp"):
    from mta.core.config import Config
    return Config(home=Path(home)).with_project(project)


def _digest(cfg, text: str):
    from mta.core.digest import digest
    d = Path(cfg.home).parent / ("src_" + cfg.project)
    d.mkdir(parents=True, exist_ok=True)
    (d / "doc.txt").write_text(text, encoding="utf-8")
    return digest(cfg, [str(d)], reset=True)


_CORPUS = "Helios Corporation operates the Nevada Power Grid across the desert region.\n"


def test_entity_hit_carries_pointer_only_spans(tmp_path):
    from mta.core.recall import recall
    cfg = _cfg(tmp_path / "h")
    _digest(cfg, _CORPUS)
    out = recall(cfg, "Helios Nevada operates grid")
    assert out["status"] == "ok"
    spanned = [h for h in out["hits"] if h["kind"] == "entity" and h.get("spans")]
    assert spanned, "expected an entity hit with provenance spans"
    for h in spanned:
        assert len(h["spans"]) <= 5                      # capped
        for sp in h["spans"]:
            assert set(sp) <= {"doc", "start", "end"}    # pointer-only — never carries text
            md = (cfg.markdown_dir / (sp["doc"] + ".md")).read_text(
                encoding="utf-8", errors="replace")
            assert isinstance(sp["start"], int)
            assert 0 <= sp["start"] < sp["end"] <= len(md)
            assert md[sp["start"]:sp["end"]].strip()     # points at real content


def test_spans_are_computed_at_query_time_not_stored_in_the_index(tmp_path):
    """The recall meta + BM25 index stay span-free — spans are derived from graph.json on
    each query, so the token-free stored index is unchanged and no re-digest is needed."""
    from mta.core.store import load_meta, load_bm25_index
    cfg = _cfg(tmp_path / "h")
    _digest(cfg, _CORPUS)
    assert '"span"' not in json.dumps(load_meta(cfg), ensure_ascii=False)
    assert '"span"' not in json.dumps(load_bm25_index(cfg), ensure_ascii=False)


def test_theme_hits_have_no_spans(tmp_path):
    from mta.core.recall import recall
    cfg = _cfg(tmp_path / "h")
    _digest(cfg, _CORPUS)
    out = recall(cfg, "theme overview region grid")
    for h in out["hits"]:
        if h["kind"] == "theme":
            assert "spans" not in h


def test_federated_recall_hits_carry_spans(tmp_path):
    from mta.core.recall import recall
    home = tmp_path / "h"
    a = _cfg(home, "alpha"); b = _cfg(home, "beta")
    _digest(a, "Helios Corporation operates the Nevada Power Grid.\n")
    _digest(b, "Zephyr Industries operates the Oregon Wind Farm.\n")
    out = recall(a, "operates grid farm", projects=["alpha", "beta"])
    assert out["status"] == "ok" and out.get("federated") is True
    spanned = [h for h in out["hits"] if h["kind"] == "entity" and h.get("spans")]
    assert spanned, "federated entity hits should carry spans too"
    assert all("project" in h for h in out["hits"])


def test_recall_without_span_data_still_works(tmp_path):
    """An entity whose facts can't be located (no spans) simply omits `spans` — recall is
    otherwise unchanged and never errors."""
    from mta.core.recall import recall
    cfg = _cfg(tmp_path / "h")
    # PII-redacted digits → the fact text isn't verbatim in the .md → no span
    _digest(cfg, "Call the Helios Corporation desk on 01711 234567 about the Grid.\n")
    out = recall(cfg, "Helios Corporation desk")
    assert out["status"] == "ok"
    for h in out["hits"]:
        assert "spans" not in h or all(set(sp) <= {"doc", "start", "end"} for sp in h["spans"])
