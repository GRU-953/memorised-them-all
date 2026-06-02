"""WP-62 — recall-vector store consistency.

`clear_vectors` removes the matrix + sidecar, and a digest that yields no recall
units clears any prior vectors so a stale matrix (with refs to a previous graph)
can't linger. Fully offline (classical extraction + hashing embeddings).
"""
from __future__ import annotations

import os

os.environ.setdefault("MTA_NO_OLLAMA", "1")
os.environ.setdefault("MTA_AUTO_UPDATE", "off")
os.environ.setdefault("MTA_EXTRACT", "classical")

import numpy as np

from mta.core import digest as digest_mod
from mta.core import store
from mta.core.config import Config


def test_clear_vectors_is_idempotent(tmp_path):
    cfg = Config(home=tmp_path)
    store.save_vectors(cfg, np.zeros((2, 4), dtype=np.float32), [{"ref": "a"}, {"ref": "b"}])
    assert cfg.vectors_path.exists() and cfg.vectors_path.with_suffix(".json").exists()
    assert store.load_vectors(cfg) is not None

    store.clear_vectors(cfg)
    assert not cfg.vectors_path.exists()
    assert not cfg.vectors_path.with_suffix(".json").exists()
    assert store.load_vectors(cfg) is None
    store.clear_vectors(cfg)  # no error when already absent


def test_empty_units_digest_clears_stale_vectors(tmp_path, monkeypatch):
    cfg = Config(home=tmp_path)
    doc = tmp_path / "doc.txt"
    doc.write_text("Acme Corporation signed a contract with Globex Industries in Paris.\n",
                   encoding="utf-8")

    # First digest builds a graph + recall vectors.
    r1 = digest_mod.digest(cfg, [str(doc)], reset=True, fast=True)
    assert r1["status"] == "ok"
    assert cfg.vectors_path.exists(), "a normal digest should produce recall vectors"

    # A re-digest that yields no recall units must clear the prior vectors (so recall
    # can't return refs into a graph that no longer contains them).
    monkeypatch.setattr(digest_mod, "_recall_units", lambda graph_doc: ([], []))
    r2 = digest_mod.digest(cfg, [str(doc)], reset=True, fast=True)
    assert r2["status"] == "ok"
    assert not cfg.vectors_path.exists(), "empty-units digest must clear stale vectors"
    assert store.load_vectors(cfg) is None
