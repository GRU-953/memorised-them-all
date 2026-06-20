"""WP-89 — the token-free invariant is a BYTE guarantee (TF-1 Critical + TF-2 High).

Before this WP, recall/overview never length-clamped the ``label`` field, and the
"600/1200" caps on ``text``/``synopsis`` were *character* slices — so a Bengali corpus
(≈3 bytes/char), and especially an uncapped Bengali entity/theme label, leaked hundreds
of KB into Claude's context (measured 394 KB recall + 157 KB overview). These tests pin
the fix: every string field recall/overview echo back is capped in UTF-8 BYTES, and a
worst-case Bengali store stays tiny.

Fully deterministic, model-free; runs on the standard CI matrix (no conversion deps).
"""
from __future__ import annotations

import json
import os

os.environ.setdefault("MTA_AUTO_UPDATE", "off")

import numpy as np

from mta.core import recall as R

BN = "অত্যন্তগুরুত্বপূর্ণপ্রতিষ্ঠান"  # one long Bengali token, 3 bytes/char


def _cfg(tmp_path, project="tf"):
    os.environ["MTA_HOME"] = str(tmp_path)
    from mta.core.config import load
    return load().with_project(project)


def _result_bytes(obj) -> int:
    return len(json.dumps(obj, ensure_ascii=False).encode("utf-8"))


# ---- unit: the byte clipper never splits a codepoint and honours the budget ----

def test_clip_bytes_never_splits_codepoint():
    long_bn = BN * 50
    out = R._clip_bytes(long_bn, 100)
    assert len(out.encode("utf-8")) <= 100
    assert long_bn.startswith(out)            # it's a clean prefix
    assert "�" not in out                # no broken/replacement char
    # under-budget input is returned verbatim
    assert R._clip_bytes("hi", 100) == "hi"
    assert R._clip_bytes(None, 100) == ""


def test_clip_bytes_is_total_on_edge_inputs():
    # never raises crossing the tool boundary (e.g. memory_overview on a corrupt store)
    assert R._clip_bytes("hello", 0) == ""        # non-positive cap → empty (not end-slice)
    assert R._clip_bytes("hello", -5) == ""
    assert R._clip_bytes(12345, 100) == "12345"   # non-str field coerced, no AttributeError
    assert R._clip_bytes(["x"], 100) == "['x']"


def test_hit_clamps_label_text_and_docs_in_bytes():
    unit = {"kind": "entity", "label": BN * 80, "text": BN * 80,
            "docs": [(BN * 40) + ".pdf"] * 12}
    h = R._hit(unit, 1.0)
    assert len(h["label"].encode("utf-8")) <= R._MAX_LABEL
    assert len(h["text"].encode("utf-8")) <= R._MAX_HIT_TEXT
    assert len(h["docs"]) <= R._MAX_HIT_DOCS
    assert all(len(d.encode("utf-8")) <= R._MAX_DOC_NAME for d in h["docs"])
    assert h["doc_count"] == 12               # full count still reported


# ---- integration: worst-case Bengali store stays tiny through recall/overview ----

def _craft_huge_store(cfg, n_units=60, n_themes=25):
    from mta.core import store
    cfg.ensure_dirs()
    # Each unit carries an oversized Bengali label + text + long doc names — exactly the
    # shape that blew up before the cap.
    meta = []
    for i in range(n_units):
        meta.append({"kind": "entity", "ref": f"e{i}",
                     "label": f"{BN}{i} " * 200,
                     "text": f"{BN} প্রকল্প {i} " * 200,
                     "docs": [f"{BN}-নথি-{i}.pdf"] * 8})
    matrix = np.zeros((len(meta), 256), dtype="float32")
    store.save_vectors(cfg, matrix, meta)
    communities = [{"id": f"c{i}", "label": f"{BN}-থিম-{i} " * 100,
                    "summary": f"{BN} সারাংশ {i} " * 200} for i in range(n_themes)]
    store.save_graph(cfg, {"version": 1, "nodes": [], "edges": [],
                           "communities": communities,
                           "synopsis": f"{BN} সারসংক্ষেপ " * 500,
                           "stats": {"mode": "deterministic"}})


def test_recall_result_is_byte_bounded_on_bengali(tmp_path):
    cfg = _cfg(tmp_path, "tf_recall")
    _craft_huge_store(cfg)
    out = R.recall(cfg, f"{BN} প্রকল্প", k=50)
    assert out["status"] == "ok" and out["hits"]
    for h in out["hits"]:
        assert len(h["label"].encode("utf-8")) <= R._MAX_LABEL
        assert len(h["text"].encode("utf-8")) <= R._MAX_HIT_TEXT
        for d in h["docs"]:
            assert len(d.encode("utf-8")) <= R._MAX_DOC_NAME
    assert len(out["synopsis"].encode("utf-8")) <= R._MAX_SYNOPSIS
    # The whole tool result must stay tiny even at the k=50 ceiling on a Bengali corpus
    # (was ~394 KB before the fix).
    total = _result_bytes(out)
    assert total < 100_000, f"recall result {total} bytes exceeds the token-free budget"


def test_overview_result_is_byte_bounded_on_bengali(tmp_path):
    cfg = _cfg(tmp_path, "tf_overview")
    _craft_huge_store(cfg)
    out = R.overview(cfg)
    assert out["status"] == "ok"
    assert len(out["synopsis"].encode("utf-8")) <= R._MAX_SYNOPSIS
    assert len(out["themes"]) <= 20
    for t in out["themes"]:
        assert len(t["label"].encode("utf-8")) <= R._MAX_LABEL
        assert len(t["summary"].encode("utf-8")) <= R._MAX_HIT_TEXT
    total = _result_bytes(out)
    assert total < 64_000, f"overview result {total} bytes exceeds the token-free budget"


# ---- the overlap-stop fallback: an all-common-word query isn't force-declined ----

def test_all_common_word_query_keeps_a_real_hit_confident():
    # "data report information" are all in _OVERLAP_STOP; before the fallback the filtered
    # query set was empty so a genuine match still read low-confidence.
    assert R._lexical_overlap("data report information", "annual data report summary") >= 1
    # a genuinely off-topic all-common-word query still scores 0
    assert R._lexical_overlap("data report", "zebra quantum chromodynamics") == 0
