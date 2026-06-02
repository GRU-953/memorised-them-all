"""WP-31 — the eval harness gates offline retrieval quality (A10).

Loads eval/run_eval.py by path (the dir isn't a package, and `eval` shadows a
builtin), digests the committed reference corpus offline, and asserts recall@k
clears the calibrated floor. Runs on the standard CI matrix.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _load_harness():
    spec = importlib.util.spec_from_file_location("mta_eval", REPO / "eval" / "run_eval.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_eval_harness_meets_floor(tmp_path):
    h = _load_harness()
    m = h.run(tmp_path)
    floor = float(h.GOLDEN["recall_at_k_floor"])
    assert m["converted"] == m["corpus_files"]          # every corpus file converted
    assert m["entities"] > 0
    assert m["embed_mode"] == "hash"                    # exercising the offline path
    assert m["recall_at_k"] >= floor, (m["recall_at_k"], floor, m["per_query"])
