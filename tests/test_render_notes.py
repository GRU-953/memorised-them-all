"""WP-93 — per-document notes must use the collision-free, length-clamped output stem.

`write_doc_memories` keyed the note filename off the raw SOURCE basename, so two docs
sharing a basename (a/README.md + b/README.md) overwrote each other's note (silent loss of
a browseable export), and an over-long source basename raised an uncaught OSError that
aborted an otherwise-successful digest AFTER the canonical store was committed. The fix
reuses `_doc_key(d)` (derived from the de-duplicated, clamped `d["output"]`).

Deterministic, model-free; standard CI matrix.
"""
from __future__ import annotations

import os

os.environ.setdefault("MTA_AUTO_UPDATE", "off")

from mta.core import render


def _cfg(tmp_path, project):
    os.environ["MTA_HOME"] = str(tmp_path)
    from mta.core.config import load
    return load().with_project(project)


def test_same_basename_notes_do_not_collide(tmp_path):
    cfg = _cfg(tmp_path, "rnd")
    cfg.ensure_dirs()
    doc = {
        "project": "rnd", "synopsis": "s", "stats": {},
        "nodes": [{"id": "e0", "label": "X", "docs": ["README", "README-2"], "facts": []}],
        "communities": [],
        "documents": [
            {"name": "a/README.md", "output": "README.md", "status": "ok",
             "method": "text", "chars": 5},
            {"name": "b/README.md", "output": "README-2.md", "status": "ok",
             "method": "text", "chars": 5},
        ],
    }
    n = render.write_doc_memories(cfg, doc)
    assert n == 2
    files = sorted(p.name for p in cfg.memory_dir.glob("*.md"))
    assert files == ["README-2.md", "README.md"]   # two distinct notes, neither overwritten


def test_long_source_basename_does_not_abort(tmp_path):
    cfg = _cfg(tmp_path, "rnd2")
    cfg.ensure_dirs()
    longname = "x" * 400 + ".pdf"                   # > NAME_MAX; would OSError if used as filename
    doc = {
        "project": "rnd2", "synopsis": "", "stats": {},
        "nodes": [], "communities": [],
        "documents": [{"name": longname, "output": "x-abc123.md", "status": "ok",
                       "method": "pdf", "chars": 1}],
    }
    n = render.write_doc_memories(cfg, doc)          # must NOT raise OSError
    assert n == 1
    assert (cfg.memory_dir / "x-abc123.md").exists()
