"""WP-15 — R6 schema versioning & data migration (closes LIFE-03).

Offline; runs on the standard CI matrix (no models/converters needed).
"""
from __future__ import annotations

import json
import os

os.environ.setdefault("MTA_NO_OLLAMA", "1")
os.environ.setdefault("MTA_AUTO_UPDATE", "off")
os.environ.setdefault("MTA_EXTRACT", "classical")


def _cfg(tmp_path, project="m"):
    os.environ["MTA_HOME"] = str(tmp_path)
    from mta.core.config import load
    return load().with_project(project)


def _write_graph(cfg, version):
    from mta.core import store
    cfg.ensure_dirs()
    store._atomic_write_text(cfg.graph_path, json.dumps({
        "project": cfg.project, "version": version,
        "nodes": [{"id": "e0", "label": "Helios", "type": "org"}],
        "edges": [], "communities": [], "documents": [], "stats": {},
        "synopsis": "s"}))


def test_newer_store_is_readable_not_dropped(tmp_path):
    """LIFE-03: a store from a newer build is recall-readable, not 'no memory'."""
    from mta.core import store
    cfg = _cfg(tmp_path, "newer")
    _write_graph(cfg, store.SCHEMA_VERSION + 5)
    doc = store.load_graph(cfg)
    assert doc is not None, "a newer store must not be silently dropped"
    assert doc["nodes"][0]["label"] == "Helios"


def test_save_backs_up_incompatible_store(tmp_path):
    """A digest overwriting a newer store first backs it up (no data loss)."""
    from mta.core import store
    cfg = _cfg(tmp_path, "bak")
    _write_graph(cfg, store.SCHEMA_VERSION + 5)            # newer store on disk
    store.save_graph(cfg, {"project": cfg.project, "version": store.SCHEMA_VERSION,
                           "nodes": [], "edges": [], "communities": [],
                           "documents": [], "stats": {}, "synopsis": ""})
    backups = list((cfg.project_dir / "backups").glob("*/graph.json"))
    assert backups, "expected a backup of the overwritten newer store"
    assert json.loads(backups[0].read_text())["version"] == store.SCHEMA_VERSION + 5
    assert json.loads(cfg.graph_path.read_text())["version"] == store.SCHEMA_VERSION


def test_forward_migration_applied(tmp_path, monkeypatch):
    """An older store is forward-migrated in memory via the registry."""
    from mta.core import store
    cfg = _cfg(tmp_path, "mig")
    _write_graph(cfg, 0)                                   # older (v0) store
    monkeypatch.setitem(store._MIGRATIONS, 0,
                        lambda d: {**d, "version": 1, "migrated": True})
    doc = store.load_graph(cfg)
    assert doc["version"] == 1 and doc.get("migrated") is True
    assert doc["nodes"][0]["label"] == "Helios"            # data preserved


def test_current_store_loads_without_backup(tmp_path):
    from mta.core import store
    cfg = _cfg(tmp_path, "cur")
    _write_graph(cfg, store.SCHEMA_VERSION)
    assert store.load_graph(cfg)["version"] == store.SCHEMA_VERSION
    assert not (cfg.project_dir / "backups").exists()      # no backup for same version


def test_corrupt_version_returns_none(tmp_path):
    from mta.core import store
    cfg = _cfg(tmp_path, "corr")
    cfg.ensure_dirs()
    store._atomic_write_text(cfg.graph_path,
                             json.dumps({"version": "not-a-number", "nodes": []}))
    assert store.load_graph(cfg) is None
