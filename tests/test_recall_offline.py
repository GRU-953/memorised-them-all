"""WP-30 — offline recall reliability (DOC-01) + top_score consistency (RECALL-03).

Offline (hashing embeddings); runs on the standard CI matrix.
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
    cfg.recall_min_score = 0.99                 # impossibly high for hashing cosine
    from mta.core.recall import recall
    out = recall(cfg, "Aurora", k=5)
    assert out["hits"] == []                    # the floor filtered everything
    assert out["low_confidence"] is True
    assert out["top_score"] == 0.0              # matches the (empty) returned hits
    assert out["raw_top_score"] >= out["top_score"]   # pre-floor best preserved
