"""WP-30 — deterministic recall reliability (DOC-01) + top_score consistency (RECALL-03).

Fully deterministic (model-free hashing embeddings); runs on the standard CI matrix.
"""
from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("MTA_NO_OLLAMA", "1")
os.environ.setdefault("MTA_AUTO_UPDATE", "off")
os.environ.setdefault("MTA_EXTRACT", "classical")

REPO = Path(__file__).resolve().parents[1]
SAMPLE = REPO / "sample"


def _cfg(tmp_path, project="r"):
    os.environ["MTA_HOME"] = str(tmp_path)
    from mta.core.config import load
    return load().with_project(project)


def _digest(cfg):
    from mta.core.digest import digest
    return digest(cfg, [str(SAMPLE)])


def test_lexical_overlap_helper():
    from mta.core.recall import _lexical_overlap
    assert _lexical_overlap("Project Aurora lead", "Aurora is led by Marsh") >= 1
    assert _lexical_overlap("zebra quantum", "Aurora Helios Reykjavik") == 0
    assert _lexical_overlap("", "anything") == 0


def test_embedder_is_deterministic_hash(tmp_path):
    """The Embedder is always the model-free deterministic hashing embedding:
    mode=='hash', a fixed 256-d output (salvaged from the deleted test_backends.py)."""
    from mta.core.config import Config
    from mta.core.embed import Embedder
    emb = Embedder(Config(home=tmp_path))
    mat = emb.embed(["hello world"])
    assert emb.mode == "hash"
    assert mat.shape[1] == 256                      # deterministic hashing dimension
    # Same text → byte-identical vector across instances (determinism).
    again = Embedder(Config(home=tmp_path)).embed(["hello world"])
    assert (mat == again).all()


def test_offline_offtopic_is_low_confidence(tmp_path):
    """An off-topic query (no corpus terms) is flagged low-confidence — offline,
    with no model at all (DOC-01). Previously low_confidence was hardcoded False."""
    cfg = _cfg(tmp_path, "off")
    _digest(cfg)
    from mta.core.recall import recall
    out = recall(cfg, "xylophone zebra quantum chromodynamics", k=5)
    assert out["status"] == "ok"
    assert out["low_confidence"] is True


def test_low_confidence_matches_top_hit_overlap(tmp_path):
    """low_confidence is consistent with the returned top hit's lexical overlap
    (robust to hashing rank noise)."""
    cfg = _cfg(tmp_path, "match")
    _digest(cfg)
    from mta.core.recall import _lexical_overlap, recall
    q = "Aurora Helios Reykjavik Marsh Vptr"
    out = recall(cfg, q, k=5)
    assert out["hits"]
    expected_low = _lexical_overlap(q, out["hits"][0].get("text", "")) == 0
    assert out["low_confidence"] == expected_low


def test_min_score_floor_applies_offline(tmp_path):
    """MTA_RECALL_MIN_SCORE now filters on the hashing path (was silently ignored),
    and top_score reflects the RETURNED hits (RECALL-03)."""
    cfg = _cfg(tmp_path, "floor")
    _digest(cfg)
    cfg.recall_min_score = 99999                # impossibly high for the BM25 scale
    from mta.core.recall import recall
    out = recall(cfg, "Aurora", k=5)
    assert out["hits"] == []                    # the floor filtered everything
    assert out["low_confidence"] is True
    assert out["top_score"] == 0.0              # matches the (empty) returned hits
    assert out["raw_top_score"] >= out["top_score"]   # pre-floor best preserved


def test_bm25_ranker_relevance_and_bengali():
    """BM25 lexical recall (v2.2.0): ranks the on-topic unit first, returns nothing for
    an off-topic query (→ low_confidence), and matches Bengali via NFC tokenisation."""
    from mta.core.recall import _bm25_rank, _tokens
    assert _tokens("ব্র্যাক প্রোগ্রাম")                          # Bengali tokenises (\w + NFC)
    meta = [
        {"kind": "entity", "label": "Nordic Grid Authority",
         "text": "The Nordic Grid Authority approved Project Aurora in Reykjavik."},
        {"kind": "entity", "label": "Helios Energy",
         "text": "Helios Energy funded the geothermal plant expansion."},
        {"kind": "entity", "label": "আল্ট্রা-পুওর গ্র্যাজুয়েশন প্রোগ্রাম",
         "text": "ব্র্যাক আল্ট্রা-পুওর গ্র্যাজুয়েশন প্রোগ্রাম ভোলা জেলায় পরিচালনা করে।"},
    ]
    rk = _bm25_rank("who approved Project Aurora", meta, 3)
    assert rk and meta[rk[0][1]]["label"] == "Nordic Grid Authority", rk
    assert _bm25_rank("xylophone quantum chromodynamics", meta, 3) == []   # off-topic
    rb = _bm25_rank("ব্র্যাক প্রোগ্রাম", meta, 3)                          # Bengali query
    assert rb and any("ঀ" <= c <= "৿" for c in meta[rb[0][1]]["label"]), rb


def test_bm25_recall_end_to_end(tmp_path):
    """End-to-end: a relevant query is confident, an off-topic one is declinable."""
    cfg = _cfg(tmp_path, "bm25e2e")
    _digest(cfg)
    from mta.core.recall import recall
    r = recall(cfg, "who leads Project Aurora", k=3)
    assert r["status"] == "ok" and not r["low_confidence"] and r["hits"]
    assert recall(cfg, "xylophone quantum chromodynamics zzzq", k=3)["low_confidence"] is True
