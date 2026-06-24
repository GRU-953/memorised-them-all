"""v3.0.0 — "Living memory + interchange" contract tests.

Covers incremental digest (content-hash manifest, skip-unchanged, prune-removed, byte-
identical output), secure forget, GraphML/CSV exports, and memory diff/import/merge. All
offline, deterministic, model-free — runs on the standard CI matrix.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("MTA_AUTO_UPDATE", "off")


def _cfg(home, project="v3"):
    from mta.core.config import Config
    # convert_timeout=0 → in-process conversion (no spawn pool sockets); text files use the
    # deterministic inline path regardless.
    return Config(home=Path(home)).with_project(project)


def _corpus(d: Path) -> Path:
    d.mkdir(parents=True, exist_ok=True)
    (d / "alpha.txt").write_text(
        "Helios Corporation operates the Helios solar grid in Nevada.\n"
        "Director Mira Chen approved the Aurora expansion.\n", encoding="utf-8")
    (d / "beta.md").write_text(
        "# Beta\nProject Aurora is led by Mira Chen at the Helios facility in Reno.\n",
        encoding="utf-8")
    return d


def _digest(cfg, paths, **kw):
    from mta.core.digest import digest
    return digest(cfg, [str(p) for p in paths], **kw)


# ---- incremental digest --------------------------------------------------------------
def test_full_then_incremental_is_byte_identical_and_skips_conversion(tmp_path):
    """A re-digest with nothing changed re-converts 0 files and produces a byte-identical
    graph.json / memory.md / bm25 index — the determinism contract holds under incremental."""
    cfg = _cfg(tmp_path / "home")
    src = _corpus(tmp_path / "docs")

    first = _digest(cfg, [src])
    assert first["status"] == "ok"
    g1 = cfg.graph_path.read_text(encoding="utf-8")
    m1 = cfg.memory_md.read_text(encoding="utf-8")
    b1 = cfg.bm25_index_path.read_bytes()
    # first run on an empty project = everything added, nothing reused
    assert first["incremental"]["added"] == 2
    assert first["incremental"]["unchanged"] == 0

    second = _digest(cfg, [src])
    assert second["status"] == "ok"
    assert second["incremental"]["enabled"] is True
    assert second["incremental"]["unchanged"] == 2          # both files reused
    assert second["incremental"]["added"] == 0
    assert second["incremental"]["updated"] == 0
    assert second["incremental"]["converted"] == 0          # ZERO re-conversions

    assert cfg.graph_path.read_text(encoding="utf-8") == g1, "graph.json not byte-identical"
    assert cfg.memory_md.read_text(encoding="utf-8") == m1, "memory.md not byte-identical"
    assert cfg.bm25_index_path.read_bytes() == b1, "bm25 index not byte-identical"


def test_incremental_equals_full_digest_of_same_corpus(tmp_path):
    """Incremental output == a fresh full digest of the same final corpus (in a clean
    project): proves incremental only changes WHICH files convert, never the result."""
    src = _corpus(tmp_path / "docs")

    inc = _cfg(tmp_path / "inc", "p")
    _digest(inc, [src])                                     # full (empty prior)
    _digest(inc, [src])                                     # incremental (all reused)

    full = _cfg(tmp_path / "full", "p")
    _digest(full, [src], reset=True)                        # a single fresh full digest

    assert inc.graph_path.read_text(encoding="utf-8") == full.graph_path.read_text(encoding="utf-8")
    assert inc.memory_md.read_text(encoding="utf-8") == full.memory_md.read_text(encoding="utf-8")


def test_incremental_reconverts_only_the_changed_file(tmp_path):
    cfg = _cfg(tmp_path / "home")
    src = _corpus(tmp_path / "docs")
    _digest(cfg, [src])

    (src / "alpha.txt").write_text("Zephyr Industries runs the Zephyr wind farm.\n",
                                   encoding="utf-8")
    res = _digest(cfg, [src])
    assert res["incremental"]["updated"] == 1               # alpha changed
    assert res["incremental"]["unchanged"] == 1             # beta untouched
    # the re-converted markdown reflects the new content
    md = "\n".join(p.read_text(encoding="utf-8") for p in cfg.markdown_dir.glob("*.md"))
    assert "Zephyr" in md and "solar grid" not in md


def test_incremental_prunes_a_removed_file(tmp_path):
    cfg = _cfg(tmp_path / "home")
    src = _corpus(tmp_path / "docs")
    _digest(cfg, [src])
    n_before = len(list(cfg.markdown_dir.glob("*.md")))
    assert n_before == 2

    (src / "beta.md").unlink()                              # delete a source file
    res = _digest(cfg, [src])
    assert res["incremental"]["removed"] == 1
    assert len(list(cfg.markdown_dir.glob("*.md"))) == 1    # its .md was pruned
    md = "\n".join(p.read_text(encoding="utf-8") for p in cfg.markdown_dir.glob("*.md"))
    assert "Reno" not in md                                 # beta's content is gone


def test_incremental_off_reconverts_everything(tmp_path):
    cfg = _cfg(tmp_path / "home")
    cfg.incremental = False
    src = _corpus(tmp_path / "docs")
    _digest(cfg, [src])
    res = _digest(cfg, [src])
    assert res["incremental"]["enabled"] is False
    assert res["incremental"]["unchanged"] == 0
    assert res["incremental"]["converted"] == 2            # all re-converted


def test_manifest_sidecar_and_v2_schema(tmp_path):
    cfg = _cfg(tmp_path / "home")
    src = _corpus(tmp_path / "docs")
    _digest(cfg, [src])

    from mta.core import store
    assert cfg.manifest_path.exists()
    entries = store.load_manifest(cfg)
    assert len(entries) == 2
    assert all("sha256" in e and "out" in e for e in entries.values())

    doc = json.loads(cfg.graph_path.read_text(encoding="utf-8"))
    assert doc["version"] == store.SCHEMA_VERSION == 2
    # every ok document carries the portable content hash
    oks = [d for d in doc["documents"] if d.get("status") == "ok"]
    assert oks and all(len(d.get("sha256", "")) == 64 for d in oks)


def test_manifest_is_not_in_the_export_bundle(tmp_path):
    """The manifest holds absolute machine-local paths → must stay out of a portable export."""
    cfg = _cfg(tmp_path / "home")
    src = _corpus(tmp_path / "docs")
    _digest(cfg, [src])
    from mta.core import render
    out = render.export_bundle(cfg, str(tmp_path / "bundle"))
    assert out["status"] == "ok"
    assert "manifest.json" not in out["copied"]
    assert not (Path(out["dest"]) / "manifest.json").exists()


# ---- secure forget -------------------------------------------------------------------
def test_secure_forget_overwrites_then_deletes(tmp_path):
    from mta.core import store
    cfg = _cfg(tmp_path / "home", "secret")
    src = _corpus(tmp_path / "docs")
    _digest(cfg, [src])
    assert cfg.project_dir.exists()

    res = store.delete_project(cfg, secure=True)
    assert res["status"] == "ok" and res["secure"] is True
    assert res["files_overwritten"] >= 1
    assert not cfg.project_dir.exists()


def test_plain_forget_still_works(tmp_path):
    from mta.core import store
    cfg = _cfg(tmp_path / "home", "plain")
    _digest(cfg, [_corpus(tmp_path / "docs")])
    res = store.delete_project(cfg)                          # no secure flag
    assert res["status"] == "ok" and "secure" not in res
    assert not cfg.project_dir.exists()


# ---- GraphML / CSV exports -----------------------------------------------------------
def test_export_includes_graphml_and_csv(tmp_path):
    import xml.etree.ElementTree as ET
    from mta.core import render
    cfg = _cfg(tmp_path / "home")
    _digest(cfg, [_corpus(tmp_path / "docs")])
    dest = tmp_path / "bundle"
    out = render.export_bundle(cfg, str(dest))
    assert out["status"] == "ok"
    for f in ("graph.graphml", "entities.csv", "relations.csv"):
        assert f in out["copied"] and (dest / f).exists()
    root = ET.parse(dest / "graph.graphml").getroot()
    ns = {"g": "http://graphml.graphdrawing.org/xmlns"}
    n_graphml = len(root.findall(".//g:node", ns))
    doc = json.loads((dest / "graph.json").read_text(encoding="utf-8"))
    assert n_graphml == len(doc["nodes"]) >= 1               # round-trips the node set
    # entities.csv has a header + one row per node
    rows = (dest / "entities.csv").read_text(encoding="utf-8").strip().splitlines()
    assert len(rows) == len(doc["nodes"]) + 1


def test_graph_exports_are_deterministic(tmp_path):
    from mta.core import render
    cfg = _cfg(tmp_path / "home")
    _digest(cfg, [_corpus(tmp_path / "docs")])
    a, b = tmp_path / "a", tmp_path / "b"
    render.export_bundle(cfg, str(a))
    render.export_bundle(cfg, str(b))
    for f in ("graph.graphml", "entities.csv", "relations.csv"):
        assert (a / f).read_bytes() == (b / f).read_bytes(), f"{f} not deterministic"


# ---- interchange: diff / import / merge ----------------------------------------------
def _one(home, project, name, text):
    d = home.parent / f"src_{project}"
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_text(text, encoding="utf-8")
    cfg = _cfg(home, project)
    _digest(cfg, [d])
    return cfg


def test_diff_reports_document_entity_and_theme_deltas(tmp_path):
    from mta.core import interchange
    home = tmp_path / "home"
    a = _one(home, "pa", "x.txt", "Helios Corporation runs the solar grid in Nevada.\n")
    _one(home, "pb", "y.txt", "Zephyr Industries runs the wind farm in Oregon.\n")
    d = interchange.diff_memory(a, "pb")
    assert d["status"] == "ok" and d["a"] == "pa" and d["b"] == "pb"
    assert d["documents"]["only_in_a"]["count"] == 1
    assert d["documents"]["only_in_b"]["count"] == 1
    assert d["documents"]["common"] == 0
    assert d["entities"]["a_total"] >= 1 and d["entities"]["b_total"] >= 1


def test_diff_detects_changed_document_by_content_hash(tmp_path):
    from mta.core import interchange
    home = tmp_path / "home"
    a = _one(home, "ca", "shared.txt", "Alpha report about Helios Corporation.\n")
    _one(home, "cb", "shared.txt", "A wholly different report about Zephyr Industries.\n")
    d = interchange.diff_memory(a, "cb")
    assert "shared.txt" in d["documents"]["changed"]["names"]   # same name, different sha256


def test_import_restores_a_bundle_and_recalls(tmp_path):
    from mta.core import interchange, recall as rec, render
    home = tmp_path / "home"
    src = _cfg(home, "orig")
    _digest(src, [_corpus(tmp_path / "docs")])
    bundle = tmp_path / "bundle"
    render.export_bundle(src, str(bundle))

    dst = _cfg(home, "restored")
    res = interchange.import_memory(dst, str(bundle))
    assert res["status"] == "ok" and "graph.json" in res["imported"]
    assert rec.recall(dst, "Helios", k=3)["status"] == "ok"     # recall-ready

    res2 = interchange.import_memory(dst, str(bundle))           # over an existing store
    assert res2["status"] == "ok"
    assert (dst.project_dir / "backups").exists()               # prior store backed up


def test_import_rejects_a_non_bundle(tmp_path):
    from mta.core import interchange
    empty = tmp_path / "empty"; empty.mkdir()
    res = interchange.import_memory(_cfg(tmp_path / "home", "x"), str(empty))
    assert res["status"] == "error"


def test_merge_combines_corpora_and_recalls_from_both(tmp_path):
    from mta.core import interchange, recall as rec
    home = tmp_path / "home"
    _one(home, "ma", "a.txt", "Helios Corporation operates the solar grid in Nevada.\n")
    _one(home, "mb", "b.txt", "Zephyr Industries operates the wind farm in Oregon.\n")
    res = interchange.merge_memory(_cfg(home, "mc"), ["ma", "mb"], "mc")
    assert res["status"] == "ok"
    assert res["merge"]["documents"] == 2
    mc = _cfg(home, "mc")
    md = "\n".join(p.read_text(encoding="utf-8") for p in mc.markdown_dir.glob("*.md"))
    assert "Helios" in md and "Zephyr" in md
    assert rec.recall(mc, "Helios", k=3)["status"] == "ok"


def test_merge_dedups_identical_documents(tmp_path):
    from mta.core import interchange
    home = tmp_path / "home"
    same = "Helios Corporation operates the grid.\n"
    _one(home, "d1", "same.txt", same)
    _one(home, "d2", "same.txt", same)                          # byte-identical doc
    res = interchange.merge_memory(_cfg(home, "dm"), ["d1", "d2"], "dm")
    assert res["status"] == "ok" and res["merge"]["documents"] == 1   # merged once


def test_merge_missing_source_errors(tmp_path):
    from mta.core import interchange
    res = interchange.merge_memory(_cfg(tmp_path / "home", "z"), ["nope"], "z")
    assert res["status"] == "error"
