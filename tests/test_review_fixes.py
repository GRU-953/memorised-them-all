"""WP-34 — fixes from the fresh-eyes pre-release review. Offline; CI-matrix safe."""
from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor

import numpy as np

os.environ.setdefault("MTA_NO_OLLAMA", "1")
os.environ.setdefault("MTA_AUTO_UPDATE", "off")
os.environ.setdefault("MTA_EXTRACT", "classical")


def _cfg(tmp_path, project="rf"):
    os.environ["MTA_HOME"] = str(tmp_path)
    from mta.core.config import load
    return load().with_project(project)


# ---- H1: torn vector store (npz rows != json meta) ------------------------
def test_load_vectors_torn_pair_returns_none(tmp_path):
    from mta.core import store
    cfg = _cfg(tmp_path, "torn")
    cfg.ensure_dirs()
    with open(cfg.vectors_path, "wb") as f:
        np.savez_compressed(f, matrix=np.zeros((5, 4), dtype=np.float32))  # 5 rows
    cfg.vectors_path.with_suffix(".json").write_text(
        json.dumps([{"kind": "entity"}, {"kind": "theme"}]))           # 2 meta
    assert store.load_vectors(cfg) is None        # desync → treated as no memory


def test_recall_on_torn_store_does_not_crash(tmp_path):
    from mta.core.recall import recall
    cfg = _cfg(tmp_path, "torn2")
    cfg.ensure_dirs()
    with open(cfg.vectors_path, "wb") as f:
        np.savez_compressed(f, matrix=np.zeros((5, 256), dtype=np.float32))
    cfg.vectors_path.with_suffix(".json").write_text("[]")
    out = recall(cfg, "anything", k=5)
    assert out["status"] == "no_memory"           # guarded — never IndexError


# ---- H2: config.load() profile race under concurrency ---------------------
def test_concurrent_offline_profile_no_leak(tmp_path, monkeypatch):
    monkeypatch.setenv("MTA_HOME", str(tmp_path))
    monkeypatch.setenv("MTA_PROFILE", "offline")
    for k in ("MTA_NO_OLLAMA", "MTA_EXTRACT", "MTA_AUTO_UPDATE"):
        monkeypatch.delenv(k, raising=False)
    from mta.core.config import load
    with ThreadPoolExecutor(max_workers=8) as ex:
        flags = list(ex.map(lambda _: load().no_ollama, range(64)))
    assert all(flags), f"profile leaked under concurrent load(): {flags.count(False)}/64 False"


# ---- H3: _lexical fallback keeps the relevance contract (DOC-01) ----------
def test_lexical_fallback_contract():
    from mta.core import recall
    from mta.core.config import load
    cfg = load().with_project("lex")
    meta = [{"kind": "entity", "label": "Helios", "text": "Helios Energy in Reykjavik", "docs": []}]
    off = recall._lexical("zebra quantum", meta, 5, cfg)
    on = recall._lexical("Helios Reykjavik", meta, 5, cfg)
    for o in (off, on):
        assert {"low_confidence", "top_score", "raw_top_score", "synopsis"} <= set(o)
    assert off["low_confidence"] is True and off["hits"] == []
    assert on["low_confidence"] is False and on["hits"]


# ---- token-free: synopsis is capped ---------------------------------------
def test_synopsis_is_capped(tmp_path):
    from mta.core import store
    from mta.core.recall import _MAX_SYNOPSIS, overview, recall
    cfg = _cfg(tmp_path, "syn")
    cfg.ensure_dirs()
    store._atomic_write_text(cfg.graph_path, json.dumps({
        "project": cfg.project, "version": store.SCHEMA_VERSION, "synopsis": "x" * 5000,
        "nodes": [], "edges": [], "communities": [], "documents": [], "stats": {}}))
    with open(cfg.vectors_path, "wb") as f:
        np.savez_compressed(f, matrix=np.zeros((1, 256), dtype=np.float32))
    cfg.vectors_path.with_suffix(".json").write_text(
        json.dumps([{"kind": "theme", "label": "X", "text": "x"}]))
    assert len(overview(cfg)["synopsis"]) <= _MAX_SYNOPSIS
    assert len(recall(cfg, "x", k=1).get("synopsis", "")) <= _MAX_SYNOPSIS


# ---- M: updater rollback is re-verified before claiming success -----------
def test_updater_rollback_is_reverified(tmp_path, monkeypatch):
    from mta.core import updater
    cfg = _cfg(tmp_path, "upd")
    monkeypatch.setattr(updater, "_installed_version", lambda p: "0.1.6")
    monkeypatch.setattr(updater, "_pip", lambda *a, **k: True)           # pip "succeeds"
    monkeypatch.setattr(updater, "_imports_ok", lambda m: False)         # never imports
    r = updater.update_markitdown(cfg)
    assert r["updated"] is False and r["rolled_back"] is False           # not claimed unverified
    seq = iter([False, True])                                            # upgrade fails, rollback ok
    monkeypatch.setattr(updater, "_imports_ok", lambda m: next(seq))
    assert updater.update_markitdown(cfg)["rolled_back"] is True


# ---- Low: list_digestible never crosses the MCP boundary on bad input -----
def test_list_digestible_guards(tmp_path):
    import mta.server as srv
    assert srv.list_digestible("")["status"] == "error"
    assert srv.list_digestible(str(tmp_path / "nope"))["status"] == "not_found"
