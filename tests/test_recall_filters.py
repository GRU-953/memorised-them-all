"""v3.1 — recall power-ups: structured filters (WP-130) + multi-project recall (WP-144).

Offline, deterministic, model-free. Filters are applied AFTER ranking (relevance order
preserved) and stay token-free (the same per-field byte caps + k clamp apply).
"""
from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("MTA_AUTO_UPDATE", "off")


def _cfg(home, project="r"):
    from mta.core.config import Config
    return Config(home=Path(home)).with_project(project)


def _digest(cfg, *files):
    from mta.core.digest import digest
    return digest(cfg, [str(f) for f in files])


def _two_file_corpus(d: Path) -> Path:
    d.mkdir(parents=True, exist_ok=True)
    (d / "alpha.txt").write_text(
        "Helios Corporation operates the solar grid in Nevada. "
        "Director Mira Chen approved the Aurora expansion.\n", encoding="utf-8")
    (d / "beta.txt").write_text(
        "Zephyr Industries operates the wind farm in Oregon. "
        "Engineer Sam Park leads the turbine programme.\n", encoding="utf-8")
    return d


# ---- WP-130: doc filter --------------------------------------------------------------
def test_doc_filter_limits_hits_to_one_source(tmp_path):
    from mta.core import recall as rec
    cfg = _cfg(tmp_path / "h")
    _digest(cfg, _two_file_corpus(tmp_path / "d"))

    out = rec.recall(cfg, "operates", doc="alpha.txt")
    assert out["status"] == "ok"
    assert out.get("filters") == {"doc": "alpha.txt"}
    assert out["hits"], "expected at least one hit citing alpha.txt"
    for h in out["hits"]:
        names = {Path(x).name for x in h.get("docs", [])}
        assert "alpha.txt" in names              # every hit cites the requested document
        assert "beta.txt" not in names


def test_doc_filter_matches_by_basename(tmp_path):
    from mta.core import recall as rec
    cfg = _cfg(tmp_path / "h")
    _digest(cfg, _two_file_corpus(tmp_path / "d"))
    # a full/relative path still matches on its basename
    out = rec.recall(cfg, "operates", doc="/somewhere/else/beta.txt")
    assert out["status"] == "ok"
    for h in out["hits"]:
        assert "beta.txt" in {Path(x).name for x in h.get("docs", [])}


# ---- WP-130: entity_type filter ------------------------------------------------------
def test_entity_type_filter_returns_only_that_type(tmp_path):
    from mta.core import recall as rec
    from mta.core.store import load_meta
    cfg = _cfg(tmp_path / "h")
    _digest(cfg, _two_file_corpus(tmp_path / "d"))

    meta = load_meta(cfg)
    types = {u.get("type") for u in meta if u.get("kind") == "entity" and u.get("type")}
    assert types, "entity units should carry a v3.1 'type' field after digest"
    a_type = sorted(types)[0]

    out = rec.recall(cfg, "operates grid wind farm Nevada Oregon", entity_type=a_type)
    assert out["status"] == "ok" and out.get("filters") == {"entity_type": a_type}
    for h in out["hits"]:
        assert h["kind"] == "entity"
        # the returned unit must be of the requested type (cross-checked via meta by label)
        matching = [u for u in meta if u.get("label") == h["label"]
                    and u.get("kind") == "entity"]
        assert matching and all(u.get("type") == a_type for u in matching)


def test_filters_are_additive_no_regression_without_them(tmp_path):
    from mta.core import recall as rec
    cfg = _cfg(tmp_path / "h")
    _digest(cfg, _two_file_corpus(tmp_path / "d"))
    out = rec.recall(cfg, "Helios")                  # no filters → unchanged contract
    assert out["status"] == "ok" and "filters" not in out
    assert "hits" in out and "low_confidence" in out


# ---- WP-144: multi-project (federated) recall ----------------------------------------
def test_federated_recall_draws_from_multiple_projects(tmp_path):
    from mta.core import recall as rec
    home = tmp_path / "h"
    a = _cfg(home, "alpha"); b = _cfg(home, "beta")
    da = tmp_path / "da"; da.mkdir(); (da / "a.txt").write_text(
        "Helios Corporation operates the solar grid.\n", encoding="utf-8")
    db = tmp_path / "db"; db.mkdir(); (db / "b.txt").write_text(
        "Zephyr Industries operates the wind farm.\n", encoding="utf-8")
    _digest(a, da); _digest(b, db)

    out = rec.recall(a, "operates", projects=["alpha", "beta"])
    assert out["status"] == "ok" and out.get("federated") is True
    assert out["projects"] == ["alpha", "beta"]
    assert out["hits"], "federated query should return hits"
    assert all("project" in h for h in out["hits"])      # every hit is tagged
    assert {h["project"] for h in out["hits"]} == {"alpha", "beta"}  # drawn from BOTH


def test_federated_recall_dedups_and_slugifies_project_names(tmp_path):
    from mta.core import recall as rec
    home = tmp_path / "h"
    a = _cfg(home, "alpha")
    da = tmp_path / "da"; da.mkdir(); (da / "a.txt").write_text(
        "Helios Corporation operates the solar grid.\n", encoding="utf-8")
    _digest(a, da)
    # "Alpha" slugifies to "alpha"; duplicates collapse
    out = rec.recall(a, "Helios", projects=["Alpha", "alpha", "  "])
    assert out["status"] == "ok" and out["projects"] == ["alpha"]


def test_federated_recall_skips_empty_projects(tmp_path):
    from mta.core import recall as rec
    home = tmp_path / "h"
    a = _cfg(home, "alpha")
    da = tmp_path / "da"; da.mkdir(); (da / "a.txt").write_text(
        "Helios Corporation operates the solar grid.\n", encoding="utf-8")
    _digest(a, da)
    out = rec.recall(a, "Helios", projects=["alpha", "does-not-exist"])
    assert out["status"] == "ok" and out["projects"] == ["alpha", "does-not-exist"]
    assert all(h["project"] == "alpha" for h in out["hits"])  # the missing one contributes nothing
