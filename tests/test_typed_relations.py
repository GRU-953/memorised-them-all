"""Theme-Z kickoff — WP-120: rule-based, verb-mediated TYPED + DIRECTED relations.

Additive and deterministic: a verb cue in the short gap between two entities promotes that
edge to a directed typed relation (`relations: [{type, from, to}]`); everything else stays
the undirected `related_to` co-occurrence, so the graph topology / weights / communities are
unchanged. English-only, model-free. Offline.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("MTA_AUTO_UPDATE", "off")


def _cfg(home, project="tr"):
    from mta.core.config import Config
    return Config(home=Path(home)).with_project(project)


def _digest(cfg, text: str):
    from mta.core.digest import digest
    d = Path(cfg.home).parent / "src"
    d.mkdir(parents=True, exist_ok=True)
    (d / "doc.txt").write_text(text, encoding="utf-8")
    return digest(cfg, [str(d)], reset=True)


def _graph(cfg):
    return json.loads(cfg.graph_path.read_text(encoding="utf-8"))


# ---- the unit helper (no I/O) --------------------------------------------------------
def test_typed_relation_helper_directs_by_position():
    from mta.core.extract import _typed_relation
    s = "Helios Corporation operates the Nevada Power Grid."
    rtype, src, tgt = _typed_relation(s, "Helios Corporation", "Nevada Power Grid")
    assert rtype == "operates" and src == "Helios Corporation" and tgt == "Nevada Power Grid"
    # reversed argument order → same direction (subject first by sentence position)
    rtype2, src2, tgt2 = _typed_relation(s, "Nevada Power Grid", "Helios Corporation")
    assert (rtype2, src2, tgt2) == ("operates", "Helios Corporation", "Nevada Power Grid")


def test_typed_relation_helper_falls_back_to_related_to():
    from mta.core.extract import _typed_relation
    s = "Helios Corporation and Nevada Power Grid attended."     # no verb cue between
    assert _typed_relation(s, "Helios Corporation", "Nevada Power Grid") == (
        "related_to", "Helios Corporation", "Nevada Power Grid")


def test_relation_not_fired_when_entities_far_apart():
    from mta.core.extract import _typed_relation
    s = ("Helios Corporation " + "x " * 40 + "operates a plant near the Nevada Power Grid.")
    # the verb is far from either mention → stays related_to (no spurious long-range relation)
    assert _typed_relation(s, "Helios Corporation", "Nevada Power Grid")[0] == "related_to"


# ---- end-to-end through digest -------------------------------------------------------
def test_digest_emits_directed_typed_relation_in_graph(tmp_path):
    cfg = _cfg(tmp_path / "h")
    _digest(cfg, "Helios Corporation operates the Nevada Power Grid across the region.\n")
    g = _graph(cfg)
    id2label = {n["id"]: n["label"] for n in g["nodes"]}

    rels = [(e, r) for e in g["edges"] for r in e.get("relations", [])]
    assert rels, "expected at least one typed relation in the graph"
    operates = [r for _e, r in rels if r["type"] == "operates"]
    assert operates, "expected an 'operates' relation"
    r = operates[0]
    assert "Helios" in id2label.get(r["from"], "")          # subject
    assert "Nevada" in id2label.get(r["to"], "") or "Grid" in id2label.get(r["to"], "")  # object
    assert r["from"] != r["to"]


def test_cooccurrence_only_edge_has_no_relations_field(tmp_path):
    cfg = _cfg(tmp_path / "h")
    _digest(cfg, "Helios Corporation and Nevada Power Grid jointly attended the summit.\n")
    g = _graph(cfg)
    # there is an edge (they co-occur) but with no verb cue → no directed relations attached
    assert g["edges"], "entities should still co-occur into an edge"
    assert all("relations" not in e for e in g["edges"]), "no typed relations without a verb cue"


def test_typed_relations_are_deterministic(tmp_path):
    """Byte-identical graph.json across two fresh digests of the same cued corpus ([C1])."""
    text = "Helios Corporation operates the Nevada Power Grid. Mira Chen leads Project Aurora.\n"
    a = _cfg(tmp_path / "a", "p"); b = _cfg(tmp_path / "b", "p")
    _digest(a, text); _digest(b, text)
    assert a.graph_path.read_text(encoding="utf-8") == b.graph_path.read_text(encoding="utf-8")
    # and the relations field is genuinely present (so we're testing a non-trivial case)
    assert any(e.get("relations") for e in _graph(a)["edges"])
