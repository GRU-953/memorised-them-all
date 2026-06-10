"""WP-87 — fixes from the expert-panel audit of the completed UPGP memory.

All deterministic / model-free. Covers: (1) beneficiary-PII suppression from facts &
theme summaries, (2) Bijoy-ASCII mojibake recovery on markitdown text, (3) the 'Unnamed'
spreadsheet-column blocklist, (4) Bangladesh district/division gazetteer typing, and
(5) the stopword-filtered off-topic recall guard.
"""
from __future__ import annotations

import os

os.environ.setdefault("MTA_NO_OLLAMA", "1")
os.environ.setdefault("MTA_EXTRACT", "classical")

from mta.core.segment import Chunk


def _chunk(text):
    return Chunk(id="c", doc="d.md", heading_path="", text=text, index=0)


# ---- (1) PII / tabular suppression -----------------------------------------
def test_is_tabular_or_pii_detects_rosters_and_phones():
    from mta.core.extract import _is_tabular_or_pii
    assert _is_tabular_or_pii("Shahidul Islam Shahin | Shirina | 80 | 17 | 017972036")
    assert _is_tabular_or_pii("Abdul Alim | গীতা রানী | 1 | ০৯ | ০১৭৮৪২৯৭৪৭১")  # Bengali phone
    assert _is_tabular_or_pii("Male | No | 24 | Rural")                        # short-cell row
    assert _is_tabular_or_pii("call me on 01799123456 today")                  # bare phone
    # legitimate prose must NOT be flagged
    assert not _is_tabular_or_pii(
        "BRAC operates the Ultra-Poor Graduation Programme in Bhola district.")
    assert not _is_tabular_or_pii("The 2023 cohort enrolled across four divisions.")


def test_redact_pii_collapses_long_digit_runs_both_scripts():
    from mta.core.extract import _redact_pii
    assert _redact_pii("call 017972036 now") == "call [number] now"
    assert "[number]" in _redact_pii("নম্বর ০১৭৮৪২৯৭৪৭১")     # Bengali numerals
    assert _redact_pii("the 2023 budget was 540 BDT") == "the 2023 budget was 540 BDT"


def test_pii_rows_never_become_facts():
    from mta.core.extract import extract_chunk
    txt = ("Rakibul islam | Rabeya Akter | 24 | 01845094240 | Male | No | Rural. "
           "Shahidul Islam | Shirina | 80 | 017972036 | Husband | Yes | Married.")
    ex = extract_chunk(_chunk(txt))
    joined = " ".join(ex.facts)
    assert "01845094240" not in joined and "017972036" not in joined, ex.facts
    assert not any("|" in f for f in ex.facts), ex.facts


def test_low_value_skips_large_beneficiary_roster():
    from mta.core.digest import _low_value
    roster = "Name Age Phone Sex Status | " + " | ".join(
        f"Person {i} | Spouse | {20 + i} | 0184509{4000 + i} | Male | No | Rural"
        for i in range(8))
    assert len(roster.split()) >= 40
    assert _low_value(roster) is True
    # narrative prose with a couple of numbers survives
    prose = ("The Ultra-Poor Graduation Programme reached 12000 households across Bhola "
             "and Rangpur in 2023 through asset transfers, weekly stipends and enterprise "
             "training that help families graduate from extreme poverty within two years. "
             "District coordinators reported strong results across the income generating "
             "activities and the community based facilitator network supported many villages.")
    assert len(prose.split()) >= 40
    assert _low_value(prose) is False


def test_community_summary_strips_pii():
    from mta.core.config import Config
    from mta.core.digest import _community_summary
    facts = ["Shahidul Islam | Shirina | 80 | 017972036 | Husband",
             "BRAC runs the graduation programme in Bhola and Rangpur."]
    out = _community_summary(facts, ["Bhola", "BRAC"], Config())
    assert "017972036" not in out
    assert "graduation programme" in out.lower()             # real fact kept


# ---- (2) Bijoy-ASCII mojibake recovery on markitdown text ------------------
def test_bijoy_mojibake_has_no_unicode_bengali_and_recovers():
    from mta.core.bangla_legacy import has_unicode_bengali, maybe_convert
    bijoy = "G‡Z e¨emv †Kgb P‡jwQj 6 e¨emv m¤úmªvi‡Yi Rb¨ MvÖn‡Ki mv‡_"
    assert has_unicode_bengali(bijoy) is False               # genuine mojibake → no real Bengali
    out, changed = maybe_convert(bijoy)                       # default 0.12 floor catches it (≈0.146)
    assert changed is True
    assert has_unicode_bengali(out) is True                  # now real Unicode Bengali


def test_real_unicode_bengali_is_not_touched():
    from mta.core.bangla_legacy import has_unicode_bengali, maybe_convert
    real = "ব্র্যাক অতিদরিদ্র গ্র্যাজুয়েশন প্রোগ্রাম পরিচালনা করে।"
    assert has_unicode_bengali(real) is True
    out, changed = maybe_convert(real, ratio=0.15)
    assert changed is False and out == real                  # already correct → untouched


# ---- (3) 'Unnamed' blocklist -----------------------------------------------
def test_unnamed_column_placeholder_dropped():
    from mta.core.extract import _UNNAMED_RE, extract_chunk
    assert _UNNAMED_RE.match("Unnamed") and _UNNAMED_RE.match("Unnamed: 3")
    assert not _UNNAMED_RE.match("Union") and not _UNNAMED_RE.match("United")
    txt = ("Unnamed: 0 and Unnamed: 1 appear in the sheet. BRAC operates the programme "
           "in Bhola. BRAC supports many districts. Bhola is one district.")
    ex = extract_chunk(_chunk(txt))
    names = {e["name"] for e in ex.entities}
    assert not any(n.lower().startswith("unnamed") for n in names), names
    assert "BRAC" in names


# ---- (4) gazetteer typing --------------------------------------------------
def test_bd_gazetteer_types_places_and_orgs():
    from mta.core.extract import _infer_type
    for d in ("Dhaka", "Bhola", "Rangpur", "Kurigram", "Habigonj", "Habiganj",
              "Barishal", "Barisal", "Cumilla", "Jashore"):
        assert _infer_type(d, "") == "place", d
    for o in ("BRAC", "UPGP", "DIUPG", "BIGD"):
        assert _infer_type(o, "") == "org", o
    # a non-gazetteer capitalised word stays "other" unless a suffix hints otherwise
    assert _infer_type("Aurora", "") == "other"


# ---- (2b) line-wise Bijoy recovery for MIXED docs --------------------------
def test_recover_mixed_converts_only_bijoy_lines():
    from mta.core.bangla_legacy import has_unicode_bengali, recover_mixed
    # an English line, two Bijoy-mojibake lines (one ASCII-heavy, density ~0.11), and an
    # already-correct Bengali line
    text = ("The programme guideline follows below.\n"
            "G‡Z e¨emv †Kgb P‡jwQj 6 e¨emv m¤úmªvi‡Yi Rb¨ MvÖn‡Ki mv‡_ mym¤ú©K ivLv\n"
            "▪ Kg©¶gZv n«vm: kvixwiK AvNvZ ev gvbwmK AZ¨vPv‡ii Kvi‡Y wbh©vwZZ e¨w³\n"
            "ব্র্যাক অতিদরিদ্র কর্মসূচি পরিচালনা করে।")
    out, changed = recover_mixed(text)
    assert changed is True
    lines = out.split("\n")
    assert lines[0] == "The programme guideline follows below."        # English untouched
    assert has_unicode_bengali(lines[1])                                # mojibake → Bengali
    assert has_unicode_bengali(lines[2])                                # ASCII-heavy Bijoy → Bengali
    assert lines[3] == "ব্র্যাক অতিদরিদ্র কর্মসূচি পরিচালনা করে।"        # real Bengali untouched


def test_recover_mixed_leaves_non_bijoy_symbol_noise_alone():
    from mta.core.bangla_legacy import recover_mixed
    # IPA / symbol junk (markitdown mis-extract) must NOT be force-converted to gibberish
    text = "ɐ ɐ ɰ ʃ ʒ\nThe 2023 cohort enrolled across four divisions of the country."
    out, changed = recover_mixed(text)
    assert changed is False and out == text


def test_recover_mixed_leaves_accent_dense_english_alone():
    from mta.core.bangla_legacy import recover_mixed
    # accent/symbol-dense English (high-byte ratio ~0.12) must NOT be converted — the
    # English-function-word guard keeps it safe even above the density floor.
    text = "Café résumé naïve — £100 at 25°C, with the ™ and © symbols included here."
    out, changed = recover_mixed(text)
    assert changed is False and out == text
    # Spanish prose (no high-byte) is also untouched
    out2, ch2 = recover_mixed("El programa de graduación alcanzó a doce mil hogares.")
    assert ch2 is False


# ---- (2c) hex / binary-blob junk rejection ---------------------------------
def test_hex_and_binary_blobs_rejected_as_entities():
    from mta.core.extract import _valid_entity
    assert not _valid_entity("FF3300FF3333FF3366FF3399FF33CCFF33FF")     # colour-code blob
    assert not _valid_entity("B8B7B6B5B4B3B2B1B0AFAEADACABAAA9A8")       # byte run
    assert not _valid_entity("BAB431EA07F209EB8C4348311481D9D3F76E3")    # hex blob
    assert _valid_entity("BRAC") and _valid_entity("Bhola") and _valid_entity("UPGP")


def test_low_value_skips_hex_and_xmp_dumps():
    from mta.core.digest import _low_value
    # 50 DISTINCT long hex tokens (a real colour-profile/base16 dump) — varied so it is
    # caught by the hex-blob rule, not the repetitive-filler rule.
    hexdump = " ".join(f"{i:012X}AABBCCDD{i:04X}" for i in range(50))
    assert len(hexdump.split()) >= 40
    assert _low_value(hexdump) is True
    xmp = ("<x:xmpmeta xmlns:x='adobe:ns:meta/'> <rdf:RDF rdf:about=''> "
           "<xapG:mode>GRAY</xapG:mode> <xapG:type>PROCESS</xapG:type> "
           + " ".join(f"swatch{i} tint{i} cyan{i}" for i in range(15)))
    assert len(xmp.split()) >= 40
    assert _low_value(xmp) is True


# ---- (2d) vetted Bengali reorder repair (রম্ন→রু only) ---------------------
def test_reorder_artifact_repair_fixes_only_safe_pattern():
    from mta.core.bangla_legacy import normalize_reorder_artifacts as N
    # the one panel-approved rule fixes common words
    assert N("গ্রম্নপ") == "গ্রুপ"          # group
    assert N("শুরম্ন") == "শুরু"            # start
    assert N("পুরম্নষ") == "পুরুষ"          # man
    assert N("করম্নন") == "করুন"            # do
    assert N("গরম্নর") == "গরুর"            # cow's
    assert N("দ্রম্নত") == "দ্রুত"          # fast
    # genuine নিম্ন (lower) family is PRESERVED — the ম্ন there is not preceded by র
    assert N("নিম্ন") == "নিম্ন"
    assert N("সর্বনিম্ন") == "সর্বনিম্ন"
    assert N("নিম্নলিখিত") == "নিম্নলিখিত"
    # mixed word: genuine নিম্ন kept, রম্ন artifact fixed
    assert N("নিম্নরম্নপ") == "নিম্নরূপ".replace("রূ", "রু")   # নিম্নরুপ (নিম্ন preserved)
    # DELIBERATELY-EXCLUDED dangerous patterns are NOT touched
    assert N("প্রত্যেক") == "প্রত্যেক"      # ে্য rule excluded
    assert N("চরণরে") == "চরণরে"            # ণরে rule excluded
    assert N("স্নান") == "স্নান" and N("স্নেহ") == "স্নেহ"   # স্ন untouched
    # English unaffected
    assert N("The group started") == "The group started"


def test_reorder_repair_runs_in_extraction():
    from mta.core.extract import extract_chunk
    from mta.core.segment import Chunk
    ex = extract_chunk(Chunk(id="c", doc="d.md", heading_path="", index=0,
        text="গ্রম্নপ মিটিংয়ে শুরম্নতে পুরম্নষ সদস্যরা গুরম্নত্বপূর্ণ আলোচনা করম্নন।"))
    joined = " ".join(ex.facts) + " " + " ".join(e["name"] for e in ex.entities)
    assert "রম্ন" not in joined, joined      # artifact gone from graph-facing text
    assert "গ্রুপ" in joined or "শুরু" in joined or "গুরুত্ব" in joined, joined


# ---- (5) stopword-filtered off-topic recall guard --------------------------
def test_recall_overlap_ignores_common_words():
    from mta.core.recall import _lexical_overlap
    # "best" alone must not bridge an off-topic query to a hit
    assert _lexical_overlap("best pizza recipe napoli", "Transferring Best Practices") == 0
    # genuine topical overlap still counts
    assert _lexical_overlap("graduation programme households",
                            "Graduation Programme targets poor households") >= 2
    # Bengali content words still count
    assert _lexical_overlap("বাল্যবিবাহ প্রতিরোধ", "বাল্যবিবাহ প্রতিরোধ কার্যক্রম") >= 1
