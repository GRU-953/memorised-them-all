"""Theme-Z — WP-123: deterministic fact salience + confidence.

Each fact in `graph.json` gains an additive `salience` (how many distinct entities it
names) and `confidence ∈ [0,1]` (higher when it explicitly names its holder, 0.5 for a
fallback attachment). Additive and deterministic: facts are NOT reordered, so recall/render
and the byte-identity contract are unaffected. Offline, model-free.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("MTA_AUTO_UPDATE", "off")


def _cfg(home, project="fs"):
    from mta.core.config import Config
    return Config(home=Path(home)).with_project(project)


def _digest(cfg, text: str):
    from mta.core.digest import digest
    d = Path(cfg.home).parent / "src"
    d.mkdir(parents=True, exist_ok=True)
    (d / "doc.txt").write_text(text, encoding="utf-8")
    return digest(cfg, [str(d)], reset=True)


def _facts(cfg):
    g = json.loads(cfg.graph_path.read_text(encoding="utf-8"))
    return [f for n in g["nodes"] for f in n.get("facts", [])]


_CORPUS = (
    "Helios Corporation partnered with the Nevada Power Grid on a new plant.\n"
    "Director Mira Chen approved the annual budget.\n"
)


def test_every_fact_has_bounded_salience_and_confidence(tmp_path):
    cfg = _cfg(tmp_path / "h")
    _digest(cfg, _CORPUS)
    facts = _facts(cfg)
    assert facts, "expected some facts"
    for f in facts:
        assert isinstance(f["salience"], int) and f["salience"] >= 0
        assert isinstance(f["confidence"], (int, float))
        assert 0.0 <= f["confidence"] <= 1.0
        # confidence follows the deterministic formula (closed set of possible values)
        assert f["confidence"] in {0.5, 0.7, 0.8, 0.9, 0.95}


def test_salience_counts_named_entities_and_sets_confidence(tmp_path):
    cfg = _cfg(tmp_path / "h")
    _digest(cfg, _CORPUS)
    facts = _facts(cfg)
    # the first sentence names TWO entities (Helios Corporation + Nevada Power Grid)
    two = [f for f in facts if "Helios" in f["text"] and "Nevada" in f["text"]]
    assert two, "expected a fact naming both entities"
    assert two[0]["salience"] == 2
    assert two[0]["confidence"] == 0.8          # round(min(0.95, 0.6 + 0.1*2), 2)


def test_more_named_entities_means_higher_confidence(tmp_path):
    cfg = _cfg(tmp_path / "h")
    _digest(cfg, _CORPUS)
    facts = _facts(cfg)
    # confidence is monotonic in salience for explicitly-named facts
    for f in facts:
        if f["salience"] >= 1:
            assert f["confidence"] == round(min(0.95, 0.6 + 0.1 * f["salience"]), 2)
        else:
            assert f["confidence"] == 0.5       # fallback attachment


def test_salience_confidence_are_deterministic(tmp_path):
    a = _cfg(tmp_path / "a", "p"); b = _cfg(tmp_path / "b", "p")
    _digest(a, _CORPUS); _digest(b, _CORPUS)
    # byte-identical graph.json across fresh digests ([C1]); fields are pure functions
    assert a.graph_path.read_text(encoding="utf-8") == b.graph_path.read_text(encoding="utf-8")
    assert all("salience" in f and "confidence" in f for f in _facts(a))


def test_recall_units_unaffected_by_the_new_fields(tmp_path):
    """salience/confidence ride graph.json only — the recall meta + bm25 index (which feed
    recall) must be byte-identical to a build without them, i.e. they don't leak into recall."""
    from mta.core.store import load_meta, load_bm25_index
    cfg = _cfg(tmp_path / "h")
    _digest(cfg, _CORPUS)
    meta = load_meta(cfg)
    blob = json.dumps(meta, ensure_ascii=False)
    assert "salience" not in blob and "confidence" not in blob   # not in recall units
    idx = load_bm25_index(cfg)
    assert "salience" not in json.dumps(idx, ensure_ascii=False)
