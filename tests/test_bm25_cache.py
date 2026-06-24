"""WP-26 (R-13/R-15) — recall-path performance: meta-only load + cached BM25 index.

The cache is a pure optimisation: recall must return byte-identical results whether it
ranks from the persisted pre-tokenised index or tokenises on the fly, and an absent /
torn / mismatched cache must degrade to the on-the-fly path (never crash, never mis-rank).
The meta-only loader must preserve `load_vectors`'s no_memory semantics. Fully offline.
"""
from __future__ import annotations

import json
import os

os.environ.setdefault("MTA_AUTO_UPDATE", "off")

import numpy as np

from mta.core import store
from mta.core.config import Config
from mta.core.recall import _bm25_rank, _bm25_rank_cached, recall


def _cfg(tmp_path):
    cfg = Config(home=tmp_path)
    cfg.ensure_dirs()
    return cfg


def _seed(cfg):
    """A tiny vector store + matching BM25 index, as a digest would write."""
    units = [
        {"kind": "theme", "ref": "c0", "label": "Nordic Grid Authority",
         "text": "The Nordic Grid Authority approved Project Aurora."},
        {"kind": "entity", "ref": "n1", "label": "Project Aurora",
         "text": "Project Aurora is led by Dr. Lena Marsh."},
        {"kind": "entity", "ref": "n2", "label": "ঢাকা",
         "text": "ঢাকা শহরে গ্রুপ মিটিং অনুষ্ঠিত হয়েছে।"},
    ]
    store.save_vectors(cfg, np.zeros((len(units), 4), dtype=np.float32), units)
    from mta.core.digest import _build_bm25_index
    store.save_bm25_index(cfg, _build_bm25_index(units))
    # a graph so recall returns ok (synopsis lookup)
    cfg.graph_path.write_text(json.dumps({"version": 1, "synopsis": "s",
                                          "stats": {"mode": "deterministic"},
                                          "communities": [], "nodes": []}),
                              encoding="utf-8")
    return units


# ---- R-13: cached vs on-the-fly are identical -------------------------------

def test_cached_and_onthefly_ranking_identical(tmp_path):
    cfg = _cfg(tmp_path); _seed(cfg)
    meta = store.load_meta(cfg)
    cache = store.load_bm25_index(cfg)
    for q in ("project aurora", "nordic grid", "গ্রুপ মিটিং", "who leads aurora", "xylophone"):
        assert _bm25_rank_cached(q, meta, cache, 10) == _bm25_rank(q, meta, 10), q


def test_recall_identical_with_and_without_cache(tmp_path):
    cfg = _cfg(tmp_path); _seed(cfg)
    with_cache = recall(cfg, "project aurora")
    cfg.bm25_index_path.unlink()                       # force on-the-fly
    without = recall(cfg, "project aurora")
    for key in ("hits", "top_score", "raw_top_score", "low_confidence"):
        assert with_cache[key] == without[key], key


# ---- robustness: torn / mismatched / garbage cache falls back ---------------

def test_torn_cache_falls_back(tmp_path):
    cfg = _cfg(tmp_path); meta = _seed(cfg)
    good = recall(cfg, "nordic grid")["hits"]
    for bad in ('not json{', json.dumps({"version": 1, "count": 2, "docs": [["x"], ["y"]]}),
                json.dumps({"docs": "nonsense"}), json.dumps(["wrong-shape"])):
        cfg.bm25_index_path.write_text(bad, encoding="utf-8")
        out = recall(cfg, "nordic grid")
        assert out["status"] == "ok" and out["hits"] == good   # degrades, never mis-ranks
    # and the ranker helper itself tolerates a length-mismatched cache
    assert (_bm25_rank_cached("nordic", meta, {"docs": [["only", "one"]]}, 5)
            == _bm25_rank("nordic", meta, 5))


# ---- R-15: meta-only load preserves load_vectors semantics ------------------

def test_load_meta_matches_load_vectors_meta(tmp_path):
    cfg = _cfg(tmp_path); _seed(cfg)
    assert store.load_meta(cfg) == store.load_vectors(cfg)[1]


def test_load_meta_no_memory_semantics(tmp_path):
    cfg = _cfg(tmp_path)
    assert store.load_meta(cfg) is None                       # nothing digested
    _seed(cfg)
    assert store.load_meta(cfg) is not None
    # WP-181a: a bare sidecar (no vectors.npz) is now a VALID numpy-free store, not "torn"
    # — recall reads the sidecar, never the matrix — so load_meta still returns it.
    cfg.vectors_path.unlink()
    assert store.load_meta(cfg) is not None
    # The real no_memory signals: the sidecar is gone, or it's an empty/garbage list.
    cfg.vectors_path.with_suffix(".json").unlink()
    assert store.load_meta(cfg) is None
    cfg.vectors_path.with_suffix(".json").write_text("[]", encoding="utf-8")
    assert store.load_meta(cfg) is None                       # empty sidecar = no_memory


def test_recall_never_loads_matrix(tmp_path, monkeypatch):
    """recall must rank without np.load-ing the embedding matrix (R-15)."""
    cfg = _cfg(tmp_path); _seed(cfg)
    monkeypatch.setattr(np, "load", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("recall loaded the vectors matrix")))
    out = recall(cfg, "project aurora")
    assert out["status"] == "ok" and out["hits"]


# ---- clear/reset also drop the index ----------------------------------------

def test_oversize_cache_is_refused_and_recall_falls_back(tmp_path):
    cfg = _cfg(tmp_path); _seed(cfg)
    cfg.max_file_mb = 1                                        # 1 MB cap
    good = recall(cfg, "project aurora")["hits"]
    # a >1 MB bm25_index.json (e.g. hostile/huge copied store) must be refused, not OOM-loaded
    cfg.bm25_index_path.write_text('{"version":1,"count":1,"docs":[["x"]]}' + " " * (1_100_000),
                                   encoding="utf-8")
    assert store.load_bm25_index(cfg) is None                 # size-gated
    assert recall(cfg, "project aurora")["hits"] == good      # falls back to on-the-fly, still ok


def test_oversize_graph_reads_as_no_memory(tmp_path):
    cfg = _cfg(tmp_path); _seed(cfg)
    cfg.max_file_mb = 1
    cfg.graph_path.write_text('{"version":1,"synopsis":"' + "x" * 1_100_000 + '"}', encoding="utf-8")
    assert store.load_graph(cfg) is None                      # refused → overview/recall no_memory


def test_clear_vectors_removes_bm25_index(tmp_path):
    cfg = _cfg(tmp_path); _seed(cfg)
    assert cfg.bm25_index_path.exists()
    store.clear_vectors(cfg)
    assert not cfg.bm25_index_path.exists()
    store.clear_vectors(cfg)                                   # idempotent
