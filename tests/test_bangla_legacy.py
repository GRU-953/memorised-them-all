"""WP-69 — legacy Bengali (Bijoy/SutonnyMJ) → Unicode conversion + the convert feature.

Fully offline (no Ollama, no network). The Bijoy input bytes are written with explicit
\\u escapes so this source stays ASCII-clean and unambiguous.
"""
from __future__ import annotations

import io
import os
import zipfile

os.environ.setdefault("MTA_NO_OLLAMA", "1")
os.environ.setdefault("MTA_AUTO_UPDATE", "off")

from mta.core import bangla_legacy as bl


# ---- core conversion fidelity ------------------------------------------------
def _no_high_byte(s: str) -> bool:
    return not any(bl._is_bijoy_letterish(ord(c)) for c in s)


def test_convert_brac():
    # "eª¨vK" (Bijoy/SutonnyMJ) → "ব্র্যাক" (BRAC). Verified against the Mukti JS oracle.
    out = bl.convert_bijoy_to_unicode("eª¨vK")
    assert out == "ব্র্যাক"   # ব্র্যাক
    assert _no_high_byte(out)


def test_maybe_convert_leaves_plain_english():
    # convert_bijoy_to_unicode() assumes its input IS Bijoy (it is only ever called on
    # font- or density-confirmed runs), so it will garble English by design. The SAFE
    # entry point — maybe_convert() — must leave ordinary English untouched.
    s = "Hello World, this is plain English text."
    out, changed = bl.maybe_convert(s)
    assert changed is False and out == s


# ---- detection / safety ------------------------------------------------------
def test_density_does_not_fire_on_english_punctuation():
    # em-dash, smart quotes, bullet, ©, ™ are all in the high-byte block but NOT the
    # letter-like Bijoy range → must not trigger conversion.
    s = "A normal sentence — with “smart quotes”, a bullet •, © 2026 and ™."
    assert bl.looks_like_bijoy(s) is False
    out, changed = bl.maybe_convert(s)
    assert changed is False and out == s


def test_density_fires_on_dense_bijoy():
    dense = "eª¨vK " * 10  # repeated Bijoy word → high letter-ish density
    assert bl.looks_like_bijoy(dense) is True
    _out, changed = bl.maybe_convert(dense)
    assert changed is True


# ---- font registry -----------------------------------------------------------
def test_is_bijoy_font():
    assert bl.is_bijoy_font("SutonnyMJ")
    assert bl.is_bijoy_font("sutonnymj bold")
    assert bl.is_bijoy_font("NikoshMJ")          # *MJ heuristic
    assert not bl.is_bijoy_font("SutonnyOMJ")    # Unicode OpenType — excluded
    assert not bl.is_bijoy_font("Arial")
    assert not bl.is_bijoy_font("Kalpurush")     # Unicode Bengali font
    assert not bl.is_bijoy_font("")


# ---- font-aware docx delegacification ---------------------------------------
def _minimal_docx(bytes_io_runs: str) -> bytes:
    doc = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:body><w:p>' + bytes_io_runs + '</w:p></w:body></w:document>'
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", doc)
    return buf.getvalue()


def test_delegacify_docx_converts_only_bijoy_runs(tmp_path):
    runs = (
        '<w:r><w:rPr><w:rFonts w:ascii="SutonnyMJ" w:hAnsi="SutonnyMJ"/></w:rPr>'
        '<w:t>eª¨vK</w:t></w:r>'
        '<w:r><w:rPr><w:rFonts w:ascii="Arial"/></w:rPr><w:t>Hello</w:t></w:r>'
    )
    src = tmp_path / "mixed.docx"
    src.write_bytes(_minimal_docx(runs))
    data, count = bl.delegacify_office(src)
    assert count == 1 and data
    xml = zipfile.ZipFile(io.BytesIO(data)).read("word/document.xml").decode("utf-8")
    assert "ব্র্যাক" in xml   # ব্র্যাক present
    assert "Hello" in xml                                        # English untouched
    assert "SutonnyMJ" not in xml                                # converted run retagged
    assert "Nikosh" in xml


def test_delegacify_skips_non_office(tmp_path):
    p = tmp_path / "note.txt"; p.write_text("hi", encoding="utf-8")
    assert bl.delegacify_office(p) == (None, 0)


# ---- the standalone convert-to-markdown feature ------------------------------
def test_extract_scrubs_qwen3_special_tokens():
    # qwen3 can emit <tool_call>/ChatML/<think> control tokens that must never end up
    # inside an extracted entity/fact (real leak found digesting Bengali docs).
    from mta.core.extract import _scrub
    assert _scrub("নি<tool_call>ম apps") == "নিম apps"
    assert _scrub("Aurora <|im_end|> Project </think>") == "Aurora Project"
    assert "tool_call" not in _scrub("a<tool_call>b</tool_call>c")
    assert _scrub("X <start_of_turn> Y <|endoftext|>") == "X Y"  # gemma / pipe tokens


def test_summary_path_also_scrubs_special_tokens(tmp_path, monkeypatch):
    # The leak fix must cover LLM summaries/synopsis too — they feed memory.md + recall.
    import mta.core.backends as backends
    from mta.core.config import Config
    from mta.core.digest import _llm_summarise
    monkeypatch.setattr(backends, "generate", lambda *a, **k: "Theme <tool_call> about X <|im_end|>")
    out = _llm_summarise("prompt", Config(home=tmp_path), None)
    assert out == "Theme about X" and "tool_call" not in out


def test_convert_to_markdown_writes_md(tmp_path):
    from mta.core.config import Config
    from mta.core.digest import convert_to_markdown
    src = tmp_path / "src"; src.mkdir()
    (src / "a.txt").write_text("Project Aurora budget approved.", encoding="utf-8")
    out = tmp_path / "out"
    res = convert_to_markdown(Config(home=tmp_path / "home"), [str(src)], out_dir=str(out))
    assert res["status"] == "ok"
    assert res["stats"]["converted"] >= 1
    assert list(out.glob("*.md"))
