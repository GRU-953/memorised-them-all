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


# ---- R-14: blocking/bucketing preserves correctness + cuts O(n²) ------------

from collections import defaultdict

from mta.core.resolve import _block_keys, _norm as _rnorm, _script


def _partition(res):
    """Clustering as a set of frozensets of normalised alias names — comparable
    regardless of cid numbering."""
    groups = defaultdict(set)
    for alias, cid in res["alias_to_cid"].items():
        groups[cid].add(alias)
    return {frozenset(v) for v in groups.values()}


def _brute_partition(names, emb):
    """Reference clustering with the TRUE full O(n²) pair scan (``_block=False``) — the
    genuine unblocked baseline that blocking must reproduce."""
    res = resolve_entities([{"name": n, "type": "other"} for n in names], emb,
                           resolve_cap=0, _block=False)
    return _partition(res)


def test_block_keys_and_script():
    # "dr lena marsh" and "lena marsh" share the prefix key for "lena" → co-bucket
    assert _block_keys("dr lena marsh", "la") & _block_keys("lena marsh", "la")
    assert "la:ple" in _block_keys("lena marsh", "la")        # prefix block
    # leading-character edits co-bucket via the SUFFIX key (the High-finding regression)
    assert _block_keys("macdonald", "la") & _block_keys("mcdonald", "la")
    assert "la:sld" in _block_keys("macdonald", "la") and "la:sld" in _block_keys("mcdonald", "la")
    assert _script("ভোলা") == "bn"
    assert _script(_rnorm("José")) == "la"
    assert _script("Москва").startswith("u")


def test_blocking_matches_full_scan_on_mixed_corpus(tmp_path):
    os.environ["MTA_HOME"] = str(tmp_path)
    emb = Embedder(Config(home=tmp_path))
    corpus = ["Helios Energy", "Helios", "Project Aurora", "project aurora", "Project  Aurora ",
              "Dr. Lena Marsh", "Lena Marsh", "Nordic Grid Authority", "NGA",
              "ভোলা", "ভালো", "ঢাকা", "ঢাকি", "নিম্ন", "নিম্নলিখিত", "রহিম", "করিম",
              "Reykjavik-1", "Reykjavik-2", "José", "Jose", "Москва",
              # leading-character edits: must still merge under blocking (regression guard)
              "MacDonald", "McDonald", "Theresa", "Teresa", "Elisabeth", "Lisabeth"]
    mentions = [{"name": n, "type": "other"} for n in corpus]
    # blocked run vs the TRUE full O(n²) scan → identical clustering (no dropped merges)
    blocked = _partition(resolve_entities(mentions, emb, resolve_cap=0))
    full = _brute_partition(corpus, emb)
    assert blocked == full
    a2c = resolve_entities(mentions, emb, resolve_cap=0)["alias_to_cid"]
    assert cid_for("MacDonald", a2c) == cid_for("McDonald", a2c)   # leading-edit merge kept
    # and the key correctness facts hold within it
    a2c = resolve_entities(mentions, emb)["alias_to_cid"]
    assert cid_for("ভোলা", a2c) != cid_for("ভালো", a2c)         # WP-90 preserved
    assert cid_for("ঢাকা", a2c) != cid_for("ঢাকি", a2c)
    assert cid_for("Helios", a2c) == cid_for("Helios Energy", a2c)   # token-share merge
    assert cid_for("Lena Marsh", a2c) == cid_for("Dr. Lena Marsh", a2c)
    assert cid_for("NGA", a2c) == cid_for("Nordic Grid Authority", a2c)  # acronym
    assert cid_for("José", a2c) == cid_for("Jose", a2c)         # accent fold
    assert cid_for("Reykjavik-1", a2c) != cid_for("Reykjavik-2", a2c)  # numbered siblings


def test_resolution_is_order_independent(tmp_path):
    os.environ["MTA_HOME"] = str(tmp_path)
    emb = Embedder(Config(home=tmp_path))
    names = ["Helios Energy", "Helios", "Lena Marsh", "Dr. Lena Marsh", "ঢাকা", "ঢাকি"]
    import random
    shuffled = names[:]; random.Random(7).shuffle(shuffled)
    p1 = _brute_partition(names, emb)
    p2 = _brute_partition(shuffled, emb)
    assert p1 == p2                                            # deterministic, order-free


def test_resolve_cap_is_configurable(tmp_path):
    os.environ["MTA_HOME"] = str(tmp_path)
    emb = Embedder(Config(home=tmp_path))
    # "Helios"/"Helios Energy" merge only via the fuzzy pass (not exact-norm).
    mentions = [{"name": n, "type": "other"} for n in ["Helios", "Helios Energy", "Xyz"]]
    merged = resolve_entities(mentions, emb, resolve_cap=0)
    assert cid_for("Helios", merged["alias_to_cid"]) == cid_for("Helios Energy", merged["alias_to_cid"])
    # cap below n → pairwise passes skip → no fuzzy merge (exact-norm/acronym still run)
    capped = resolve_entities(mentions, emb, resolve_cap=1)
    assert cid_for("Helios", capped["alias_to_cid"]) != cid_for("Helios Energy", capped["alias_to_cid"])
    # env fallback path matches the explicit arg
    os.environ["MTA_RESOLVE_MAX_NAMES"] = "1"
    try:
        env_capped = resolve_entities(mentions, emb)
        assert _partition(env_capped) == _partition(capped)
    finally:
        os.environ.pop("MTA_RESOLVE_MAX_NAMES", None)
