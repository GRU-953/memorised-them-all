"""WP-90 — entity resolution must not force-merge distinct Bengali entities (RES-1).

`_norm` previously did NFKD + strip-combining + `[^\\w]` squeeze, which deleted Bengali
vowel signs/halant and reduced words to consonant skeletons — so ভোলা (Bhola, a real
district) merged with ভালো ("good"), and ঢাকা (Dhaka) with ঢাকি (drum), corrupting the
entity graph on the flagship Bengali corpus. There was no resolve test at all. These pin
the fix: Bengali distinctness preserved, while Latin accent-folding and genuine
case/spacing variant-merging still work.

Deterministic, model-free (hash embedder); standard CI matrix.
"""
from __future__ import annotations

import os

os.environ.setdefault("MTA_AUTO_UPDATE", "off")

from mta.core.config import Config
from mta.core.embed import Embedder
from mta.core.resolve import _norm, cid_for, resolve_entities


def test_norm_preserves_bengali_distinctness():
    assert _norm("ভোলা") != _norm("ভালো")          # Bhola (place) ≠ "good"
    assert _norm("ঢাকা") != _norm("ঢাকি")            # Dhaka ≠ drum
    assert _norm("নিম্ন") == "নিম্ন"                  # halant survives, word intact
    assert _norm("নিম্ন") != _norm("নিম্নলিখিত")


def test_norm_still_folds_latin_and_compat():
    assert _norm("José") == "jose"
    assert _norm("Café") == "cafe"
    assert _norm("ﬁle") == "file"                    # compatibility fold retained
    assert _norm("  Dhaka   City ") == "dhaka city"  # case + whitespace squeeze


def _resolve(names):
    mentions = []
    for nm in names:
        mentions += [{"name": nm, "type": "other"}] * 2   # appear a couple of times
    emb = Embedder(Config(home=os.environ.get("MTA_HOME", "/tmp/mta-resolve")))
    return resolve_entities(mentions, emb)


def test_distinct_bengali_entities_stay_separate(tmp_path):
    os.environ["MTA_HOME"] = str(tmp_path)
    res = _resolve(["ভোলা", "ভালো", "ঢাকা", "ঢাকি"])
    a2c = res["alias_to_cid"]
    assert cid_for("ভোলা", a2c) != cid_for("ভালো", a2c)
    assert cid_for("ঢাকা", a2c) != cid_for("ঢাকি", a2c)
    # all four resolve to four distinct canonical nodes (no skeleton over-merge)
    assert len({cid_for(n, a2c) for n in ["ভোলা", "ভালো", "ঢাকা", "ঢাকি"]}) == 4


def test_genuine_variants_still_merge(tmp_path):
    os.environ["MTA_HOME"] = str(tmp_path)
    # case/whitespace variants of the same name must still collapse to one cid
    res = _resolve(["Project Aurora", "project aurora", "Project  Aurora "])
    a2c = res["alias_to_cid"]
    cids = {cid_for(n, a2c) for n in ["Project Aurora", "project aurora", "Project  Aurora "]}
    assert len(cids) == 1 and None not in cids
    # an exact Bengali duplicate is one entity
    res2 = _resolve(["গ্রুপ", "গ্রুপ"])
    assert len(res2["canonical"]) == 1
