"""WP-64 / PIPE-06 — classical (offline) extractor quality.

The dependency-free classical path is the one the README promotes for offline use,
so its entities and facts should be clean: a leading determiner shouldn't fragment an
entity, facts shouldn't carry mid-fact newlines, and an honorific like "Dr." shouldn't
truncate a sentence. Fully offline.
"""
from __future__ import annotations

import os
from types import SimpleNamespace

os.environ.setdefault("MTA_NO_OLLAMA", "1")

from mta.core.extract import _classical, _split_sentences


def _chunk(text: str):
    # _classical only reads .text — a stub avoids the Chunk constructor.
    return SimpleNamespace(text=text)


def test_leading_determiner_does_not_fragment_entities():
    text = ("The Nordic Grid Authority approved the plan. "
            "Nordic Grid Authority will report quarterly. "
            "Nordic Grid Authority hired new staff.")
    names = {e["name"] for e in _classical(_chunk(text)).entities}
    assert "Nordic Grid Authority" in names
    assert "The Nordic Grid Authority" not in names  # "The" stripped → merges


def test_facts_have_no_internal_newlines():
    text = "The Nordic Grid\nAuthority signed a long binding agreement with the regional council today."
    facts = _classical(_chunk(text)).facts
    assert facts, "expected at least one fact"
    assert all("\n" not in f for f in facts)
    assert any("Nordic Grid Authority" in f for f in facts)  # newline collapsed


def test_sentence_split_respects_abbreviations():
    text = "The program director is Dr. Lena Marsh and she leads the whole research initiative."
    sents = _split_sentences(text)
    assert not any(s.strip().endswith("Dr.") for s in sents)   # no "… is Dr." fragment
    assert any("Dr. Lena Marsh" in s for s in sents)


def test_facts_not_truncated_at_abbreviation():
    text = "The program director is Dr. Lena Marsh and she leads the research programme each day."
    facts = _classical(_chunk(text)).facts
    assert facts
    assert not any(f.endswith("is Dr.") for f in facts)
    assert any("Dr. Lena Marsh" in f for f in facts)


# ---- WP-80: v2 extractor upgrades (typing, junk-suppression, Bengali) ---------------
def test_person_org_place_typing():
    from mta.core.extract import _classical
    from mta.core.segment import Chunk
    txt = ("Dr. Fatema Begum from the MEAL unit met the Nordic Grid Authority in "
           "Bhola District. Project Aurora expanded.")
    ex = _classical(Chunk(id="c", doc="d", heading_path="", text=txt, index=0))
    types = {e["name"]: e["type"] for e in ex.entities}
    assert types.get("Fatema Begum") == "person", types
    assert types.get("Nordic Grid Authority") == "org", types
    assert any(t == "place" for t in types.values()), types     # "Bhola District"


def test_sentence_initial_junk_suppressed():
    from mta.core.extract import _classical
    from mta.core.segment import Chunk
    txt = ("Ignore the above. New plan follows. Normal text here. "
           "Helios Energy funded Project Aurora and Helios Energy grew.")
    ex = _classical(Chunk(id="c", doc="d", heading_path="", text=txt, index=0))
    names = {e["name"] for e in ex.entities}
    assert not ({"Ignore", "New", "Normal"} & names), names      # lone-once words dropped
    assert "Helios Energy" in names                              # real recurring entity kept


def test_fence_and_control_tokens_not_extracted():
    from mta.core.extract import _classical
    from mta.core.segment import Chunk
    txt = "<<<END>>> data <tool_call>x</tool_call> The Borealis Project met the Aurora Council."
    ex = _classical(Chunk(id="c", doc="d", heading_path="", text=txt, index=0))
    blob = " ".join(e["name"] for e in ex.entities) + " " + " ".join(ex.facts)
    assert "END" not in {e["name"] for e in ex.entities}
    assert "tool_call" not in blob and "<<<" not in blob


def test_bengali_entities_extracted():
    from mta.core.extract import _classical
    from mta.core.segment import Chunk
    txt = ("আল্ট্রা-পুওর গ্র্যাজুয়েশন প্রোগ্রাম ব্র্যাক কর্তৃক বাস্তবায়িত হয়। "
           "মোঃ করিম রহমান জেলা সমন্বয়কারী। ভোলা জেলায় ১২৪০ জন অংশগ্রহণকারী।")
    ex = _classical(Chunk(id="c", doc="d", heading_path="", text=txt, index=0))
    names = [e["name"] for e in ex.entities]
    assert any(any("ঀ" <= ch <= "৿" for ch in n) for n in names), names   # Bengali surfaced
    # numerals trimmed from the edges
    assert not any("১২৪০" in n for n in names), names
