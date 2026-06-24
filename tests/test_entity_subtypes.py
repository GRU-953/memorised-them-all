"""Theme-Z — WP-121 (schema half): deterministic entity sub-types.

A high-precision, additive refinement of the coarse `type`: org →
government/financial/education/nonprofit/company; place →
division/district/upazila/city/town/union/village/region/ward (gazetteer first). Stored on
`graph.json` nodes only when a confident cue applies (closed enums). Offline, model-free,
deterministic; recall/render are unaffected (they read label/type/facts).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("MTA_AUTO_UPDATE", "off")


def _cfg(home, project="st"):
    from mta.core.config import Config
    return Config(home=Path(home)).with_project(project)


def _digest(cfg, text: str):
    from mta.core.digest import digest
    d = Path(cfg.home).parent / "src"
    d.mkdir(parents=True, exist_ok=True)
    (d / "doc.txt").write_text(text, encoding="utf-8")
    return digest(cfg, [str(d)], reset=True)


def _nodes(cfg):
    return json.loads(cfg.graph_path.read_text(encoding="utf-8"))["nodes"]


# ---- the classifier (no I/O) ---------------------------------------------------------
def test_infer_subtype_org_place_and_none():
    from mta.core.extract import _infer_subtype as s
    assert s("Nordic Grid Authority", "org") == "government"
    assert s("Ministry of Power", "org") == "government"
    assert s("Helios Bank", "org") == "financial"
    assert s("Dhaka University", "org") == "education"
    assert s("Aurora Foundation", "org") == "nonprofit"
    assert s("Helios Corporation", "org") == "company"
    assert s("Globex Ltd", "org") == "company"
    # places: gazetteer division vs district, then keyword hints
    assert s("Dhaka", "place") == "division"
    assert s("Comilla", "place") == "district"
    assert s("Faridpur District", "place") == "district"
    assert s("Mirpur Union", "place") == "union"
    # no confident cue / non-org-place → None (field omitted)
    assert s("Helios Group", "org") is None      # "Group" is deliberately not a subtype cue
    assert s("Mira Chen", "person") is None
    assert s("Quarterly Review", "other") is None


def test_subtype_is_a_closed_enum():
    from mta.core.extract import _infer_subtype, _ORG_SUBTYPES, _PLACE_SUBTYPES
    allowed = {s for s, _ in _ORG_SUBTYPES} | {s for s, _ in _PLACE_SUBTYPES}
    assert allowed == {"government", "financial", "education", "nonprofit", "company",
                       "division", "district", "upazila", "city", "town", "union",
                       "village", "region", "ward"}


# ---- end-to-end through digest -------------------------------------------------------
def test_digest_stamps_org_subtypes_on_nodes(tmp_path):
    cfg = _cfg(tmp_path / "h")
    _digest(cfg, "The Nordic Grid Authority oversees the network. "
                 "Helios Bank financed the Aurora Foundation programme.\n")
    by_label = {n["label"]: n for n in _nodes(cfg)}
    auth = next((n for lbl, n in by_label.items() if "Authority" in lbl), None)
    assert auth and auth["type"] == "org" and auth.get("subtype") == "government"
    bank = next((n for lbl, n in by_label.items() if "Bank" in lbl), None)
    assert bank and bank.get("subtype") == "financial"


def test_subtype_is_additive_absent_when_no_cue(tmp_path):
    cfg = _cfg(tmp_path / "h")
    _digest(cfg, "Mira Chen met Sam Park about the Aurora schedule.\n")
    # person/other entities carry no subtype key (additive)
    for n in _nodes(cfg):
        if n["type"] in ("person", "other"):
            assert "subtype" not in n


def test_subtypes_are_deterministic(tmp_path):
    text = "The Nordic Grid Authority and Helios Bank funded Dhaka University.\n"
    a = _cfg(tmp_path / "a", "p"); b = _cfg(tmp_path / "b", "p")
    _digest(a, text); _digest(b, text)
    assert a.graph_path.read_text(encoding="utf-8") == b.graph_path.read_text(encoding="utf-8")
    assert any("subtype" in n for n in _nodes(a))


def test_subtype_does_not_leak_into_recall(tmp_path):
    from mta.core.store import load_meta, load_bm25_index
    cfg = _cfg(tmp_path / "h")
    _digest(cfg, "The Nordic Grid Authority and Helios Bank funded the programme.\n")
    assert '"subtype"' not in json.dumps(load_meta(cfg), ensure_ascii=False)
    assert '"subtype"' not in json.dumps(load_bm25_index(cfg), ensure_ascii=False)
