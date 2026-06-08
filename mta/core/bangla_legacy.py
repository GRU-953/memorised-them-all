"""Legacy Bengali (Bijoy / SutonnyMJ ANSI) -> Unicode conversion — pure-Python, local.

A faithful port of the Mukti converter's bijoy-to-unicode pipeline
(https://github.com/anindash15-arch/Mukti, MIT, by Aninda S Howlader):

    pre-map  ->  longest-key-first main map  ->  Unicode rearrangement  ->  post-map

plus content-based script detection. Millions of Bengali documents were typed in the
Bijoy keyboard layout with the **SutonnyMJ** family (and 138+ other ANSI fonts that
share that layout); read as text they are mojibake. This upgrades them to standard
Unicode Bengali so conversion -> digest -> recall (and OCR/embeddings) work.

No third-party deps, no network — consistent with MTA's invariants. The mapping tables
live in ``_bangla_maps.py`` (auto-generated from upstream); the algorithm is here.
"""
from __future__ import annotations

import io
import os
import re
import tempfile
import zipfile
from xml.sax.saxutils import escape as _xml_escape
from xml.sax.saxutils import unescape as _xml_unescape

from ._bangla_maps import (
    BIJOY_TO_UNICODE_MAP,
    POST_CONVERSION_MAP,
    PRE_CONVERSION_MAP,
    PRE_CONVERSION_REGEX,
)

# ---- Bengali classification sets (verbatim from Mukti src/core/rearrange.js) --------
_CONSONANTS = set(
    "কখগঘঙচছজঝঞটঠ"
    "ডঢণতথদধনপফবভ"
    "মযরলশষসহড়ঢ়"
    "য়ৎংঃঁ")
_PRE_KARS = set("িৈে")
_POST_KARS = set("াোৌৗুূীৃ")
_ALL_KARS = _PRE_KARS | _POST_KARS
_HALANT = "্"   # ্
_NUKTA = "ঁ"    # (Mukti labels this NUKTA; it is U+0981 chandrabindu)
_RA = "র"       # র


def _is_cons(c: str) -> bool: return c in _CONSONANTS
def _is_pre_kar(c: str) -> bool: return c in _PRE_KARS
def _is_post_kar(c: str) -> bool: return c in _POST_KARS
def _is_kar(c: str) -> bool: return c in _ALL_KARS
def _is_halant(c: str) -> bool: return c == _HALANT
def _is_nukta(c: str) -> bool: return c == _NUKTA
def _is_space(c: str) -> bool: return c in (" ", "\t", "\n", "\r")
def _at(t: str, i: int) -> str: return t[i] if 0 <= i < len(t) else ""


# ---- normalizer (port of normalizer.js) --------------------------------------------
def _apply_literal(text: str, pairs) -> str:
    for old, new in pairs:
        if old:
            text = text.replace(old, new)  # str.replace == JS split/join (all, literal)
    return text


_RE_FLAGS = {"i": re.I, "m": re.M, "s": re.S, "x": re.X, "u": re.U}  # 'g' is implicit in re.sub


def _compile_pre_re(triples):
    out = []
    for src, flags, rep in triples:
        f = 0
        for ch in flags or "":
            f |= _RE_FLAGS.get(ch, 0)
        out.append((re.compile(src, f), rep))
    return out


_PRE_RE = _compile_pre_re(PRE_CONVERSION_REGEX)


def _compile_main(pairs):
    lookup = dict(pairs)
    # Longest key first → greedy match (e.g. 'Av'→আ before 'A'→অ).
    keys = sorted(lookup, key=len, reverse=True)
    pattern = "|".join(re.escape(k) for k in keys if k)
    return re.compile(pattern), lookup


_MAIN_RE, _MAIN_LOOKUP = _compile_main(BIJOY_TO_UNICODE_MAP)


def _apply_main(text: str) -> str:
    return _MAIN_RE.sub(lambda m: _MAIN_LOOKUP.get(m.group(0), m.group(0)), text)


# ---- rearrangement (port of rearrange.js : rearrangeUnicodeText) -------------------
def _rearrange(text: str) -> str:
    # Split on newlines first: no reordering rule ever spans a line break (a newline
    # matches none of the consonant/kar/halant classes and stops every cluster scan),
    # so per-line processing is OUTPUT-IDENTICAL while bounding each pass's repeated
    # string rebuilds to a single line — linear in total document size, not quadratic
    # in one giant string (a multi-MB Bengali doc previously paid O(n²)).
    if "\n" in text:
        return "\n".join(_rearrange_line(line) for line in text.split("\n"))
    return _rearrange_line(text)


def _rearrange_line(text: str) -> str:
    if not text:
        return text
    text = text.replace(_HALANT + _HALANT, _HALANT)  # fix double halant

    # ── Pass 1: reph + halant reordering ──
    i = 0
    while i < len(text):
        # reph: consonant(+kars) র ্ → র ্ consonant(+kars)
        if (i > 0 and i < len(text) - 1 and _at(text, i) == _RA
                and _is_halant(_at(text, i + 1)) and not _is_halant(_at(text, i - 1))):
            check = i - 1
            while check >= 0 and _is_kar(_at(text, check)):
                check -= 1
            if check >= 0 and _is_cons(_at(text, check)):
                cluster = check
                while True:
                    if cluster - 1 < 0:
                        break
                    if (_is_halant(_at(text, cluster - 1)) and cluster - 2 >= 0
                            and _is_cons(_at(text, cluster - 2))):
                        cluster -= 2
                    else:
                        break
                text = text[:cluster] + _RA + _HALANT + text[cluster:i] + text[i + 2:]
                i = cluster + 2
                continue
        # vowel/nukta + HALANT + consonant → HALANT + consonant + vowel
        if (i > 0 and _at(text, i) == _HALANT
                and (_is_kar(_at(text, i - 1)) or _is_nukta(_at(text, i - 1)))
                and i < len(text) - 1):
            text = (text[:i - 1] + _at(text, i) + _at(text, i + 1)
                    + _at(text, i - 1) + text[i + 2:])
        # র + HALANT + vowel → vowel + র + HALANT
        if (i > 0 and i < len(text) - 1 and _at(text, i) == _HALANT
                and _at(text, i - 1) == _RA and _at(text, i - 2) != _HALANT
                and _is_kar(_at(text, i + 1))):
            text = (text[:i - 1] + _at(text, i + 1) + _at(text, i - 1)
                    + _at(text, i) + text[i + 2:])
        i += 1

    # ── Pass 2: pre-kar repositioning + composites + nukta ──
    i = 0
    while i < len(text):
        if (i < len(text) - 1 and _is_pre_kar(_at(text, i))
                and not _is_space(_at(text, i + 1))):
            temp = text[:i]
            j = 1
            while i + j < len(text) - 1 and _is_cons(_at(text, i + j)):
                if i + j < len(text) and _is_halant(_at(text, i + j + 1)):
                    j += 2
                else:
                    break
            temp += text[i + 1:i + j + 1]
            l = 0
            if _at(text, i) == "ে" and _at(text, i + j + 1) == "া":
                temp += "ো"; l = 1          # ে + া → ো
            elif _at(text, i) == "ে" and _at(text, i + j + 1) == "ৗ":
                temp += "ৌ"; l = 1          # ে + ৗ → ৌ
            else:
                temp += _at(text, i)
            temp += text[i + j + l + 1:]
            text = temp
            i += j
        # chandrabindu/nukta after a post-kar → swap
        if (i < len(text) - 1 and _is_nukta(_at(text, i))
                and _is_post_kar(_at(text, i + 1))):
            text = text[:i] + _at(text, i + 1) + _at(text, i) + text[i + 2:]
        i += 1

    return text


# ---- detection ---------------------------------------------------------------------
def _is_bn_unicode(c: str) -> bool:
    return "ঀ" <= c <= "৿"


def _is_bijoy_letterish(cp: int) -> bool:
    """High-byte ranges Bijoy/SutonnyMJ uses for LETTER glyphs — deliberately EXCLUDES
    the U+2013–U+2122 block (em/en-dash, smart quotes, •, ™, …) because those are common
    in ordinary English/Markdown and would cause false positives."""
    return ((0x00A0 <= cp <= 0x00FF) or (0x0152 <= cp <= 0x0178)
            or cp in (0x0192, 0x02C6, 0x02DC, 0x0160, 0x0161))


def has_unicode_bengali(text: str) -> bool:
    return any(_is_bn_unicode(c) for c in (text or ""))


def looks_like_bijoy(text: str, *, min_chars: int = 20, ratio: float = 0.12) -> bool:
    """True only when the text is *densely* legacy-Bijoy — a high fraction of letter-like
    high-byte characters. English text with the odd ©/°/em-dash stays well under ``ratio``,
    so this is safe to run on every document. Tunable; defaults validated on real corpora."""
    if not text:
        return False
    letters = high = 0
    for c in text:
        if c.isspace():
            continue
        letters += 1
        if _is_bijoy_letterish(ord(c)):
            high += 1
    return letters >= min_chars and (high / letters) >= ratio


# ---- public API --------------------------------------------------------------------
def convert_bijoy_to_unicode(text: str) -> str:
    """Convert Bijoy/SutonnyMJ-encoded text to Unicode Bengali (no detection — always runs)."""
    if not text:
        return text
    text = _apply_literal(text, PRE_CONVERSION_MAP)
    for rx, rep in _PRE_RE:
        text = rx.sub(rep, text)
    text = _apply_main(text)
    text = _rearrange(text)
    text = _apply_literal(text, POST_CONVERSION_MAP)
    return text


def maybe_convert(text: str, *, ratio: float = 0.12) -> tuple[str, bool]:
    """Auto-detect dense legacy-Bijoy text and convert it to Unicode Bengali.

    Conservative by design: returns ``(text, False)`` unchanged unless the content is
    *densely* Bijoy (so ordinary English/Unicode-Bengali documents are never touched).
    Returns ``(converted_text, True)`` when a conversion happened.
    """
    if not looks_like_bijoy(text, ratio=ratio):
        return text, False
    return convert_bijoy_to_unicode(text), True


# ====================================================================================
# Font-aware Office delegacification (docx / pptx / xlsx)
# ------------------------------------------------------------------------------------
# Real documents are MIXED (English in Calibri/Arial + Bengali in SutonnyMJ), and a
# pure-ASCII Bijoy word (e.g. "Avwg"→আমি) is indistinguishable from English by
# characters alone. So we convert by FONT: only runs whose font is a Bijoy-family ANSI
# font are converted; everything else is left byte-for-byte. (Names from Mukti's
# font-registry.js; the other ANSI families — Boishakhi/Proshika/Lekhoni — use different
# byte maps we do not ship, so they are deliberately skipped, not mis-converted.)
# ====================================================================================
_BIJOY_FONTS = {
    "adorsholipi", "amar bangla", "anandapatracmj", "anandapatramj",
    "arhialkhanmj", "bangla", "banglalekha", "bangsee",
    "bhagirathimj", "bhairabmj", "bijoy", "bjcfonts",
    "boishakhi", "bongshaimj", "borakmj", "borhalmj",
    "bornosoft", "brahmaputramj", "burigangamj", "chandrabaticmj",
    "chandrabatimj", "chandrabatisushreemj", "chandrabhaga", "charu chandan",
    "chaturangamj", "chitramj", "chondanamj", "destinymj",
    "dhakarchithimj", "dhanshirhimj", "dholeshwarimj", "dhonoomj",
    "dhorolamj", "gangamj", "gangaomj", "gangasagarmj",
    "ghorautramj", "goomtimj", "goraimj", "haldamj",
    "hooglymj", "jai jai din mj", "jaijaidinmj", "jomunamj",
    "jugantormj", "kailashbj", "kalindimj", "kanchanmj",
    "karnaphulimj", "keertankhulamj", "khooaimatramj", "khooaimj",
    "kirtinashamj", "kongshomatramj", "kongshomj", "kopotakshamj",
    "korotoamj", "kushiaramj", "mahouamj", "mohajong",
    "mohanondamj", "monoomj", "nobogongamj", "norsundamj",
    "padmamj", "pandulipicmj", "pandulipimj", "pinkiymj",
    "poshuromj", "probhat", "punorvabamj", "ratoolmj",
    "rinkiymj", "rinkiysushreemj", "ruposreemj", "rupshamj",
    "samakalmj", "shaldamj", "shapla", "shonarbangla",
    "somewherein", "sugondhamj", "sumeshwarimj", "sushreemj",
    "sutonny", "sutonnycmj", "sutonnycmj bold", "sutonnycmj italic",
    "sutonnyemj", "sutonnyemj bold", "sutonnyemj italic", "sutonnymj",
    "sutonnymj bold", "sutonnymj bold italic", "sutonnymj italic", "sutonnymj regular",
    "sutonnymjbold", "sutonnysushreemj", "sutonnysushreemj bold", "sutonnysushreeomj",
    "tangonmj", "tangonmotamj", "taposhi", "teeshtamj",
    "tonni", "tonnybanglaj", "tonnymj", "tonnysushreemj",
    "tonushree", "turagmj", "turagomj", "turagsushreemj",
    "tutul", "urmeemj",
}
_UNICODE_FONT = "Nikosh"  # retag converted runs with a free Unicode Bengali font


def is_bijoy_font(name: str) -> bool:
    """True iff ``name`` is a Bijoy/SutonnyMJ-family ANSI font (the layout this module
    converts). SutonnyOMJ is a Unicode OpenType font → excluded."""
    if not name:
        return False
    n = " ".join(name.strip().lower().split())
    if "sutonnyomj" in n or "sutonny omj" in n:
        return False
    if n in _BIJOY_FONTS:
        return True
    base = n.rsplit(" ", 1)[0] if n.rsplit(" ", 1)[-1] in ("bold", "italic", "regular") else n
    if base in _BIJOY_FONTS:
        return True
    return n.endswith("mj") or "sutonny" in n  # the Bijoy universe is the "*MJ" ANSI fonts


# Per-format run / text / font / retag regexes (operate on the raw OOXML).
_W_RUN = re.compile(r"<w:r\b.*?</w:r>", re.S)
_W_TEXT = re.compile(r"(<w:t\b[^>]*>)(.*?)(</w:t>)", re.S)
_W_FONT = re.compile(r'w:(?:ascii|hAnsi|cs)="([^"]*)"')
_W_RETAG = re.compile(r'(w:(?:ascii|hAnsi|cs)=")([^"]*)(")')
_A_RUN = re.compile(r"<a:r\b.*?</a:r>", re.S)
_A_TEXT = re.compile(r"(<a:t\b[^>]*>)(.*?)(</a:t>)", re.S)
_A_FONT = re.compile(r'typeface="([^"]*)"')
_A_RETAG = re.compile(r'(typeface=")([^"]*)(")')
_X_RUN = re.compile(r"<r\b.*?</r>", re.S)
_X_TEXT = re.compile(r"(<t\b[^>]*>)(.*?)(</t>)", re.S)
_X_FONT = re.compile(r'<rFont val="([^"]*)"')
_X_RETAG = re.compile(r'(<rFont val=")([^"]*)(")')
_X_SI = re.compile(r"<si\b.*?</si>", re.S)


def _convert_text_el(m: "re.Match") -> str:
    inner = m.group(2)
    if not inner:
        return m.group(0)
    return m.group(1) + _xml_escape(convert_bijoy_to_unicode(_xml_unescape(inner))) + m.group(3)


def _delegacify_runs(xml, run_re, font_re, text_re, retag_re):
    n = [0]

    def on_run(rm):
        run = rm.group(0)
        if not any(is_bijoy_font(f) for f in font_re.findall(run)):
            return run
        n[0] += 1
        run = text_re.sub(_convert_text_el, run)
        return retag_re.sub(
            lambda fm: fm.group(1) + (_UNICODE_FONT if is_bijoy_font(fm.group(2)) else fm.group(2)) + fm.group(3),
            run)

    return run_re.sub(on_run, xml), n[0]


def _delegacify_plain_xlsx(xml):
    """Shared-string cells with no <r> runs carry no font; convert only those that are
    *densely* Bijoy (safe per short, homogeneous cells)."""
    n = [0]

    def on_si(sm):
        si = sm.group(0)
        if "<r>" in si or "<r " in si:   # rich runs already handled font-aware
            return si

        def on_t(tm):
            inner = tm.group(2)
            if not inner:
                return tm.group(0)
            conv, changed = maybe_convert(_xml_unescape(inner), ratio=0.15)
            if changed:
                n[0] += 1
                return tm.group(1) + _xml_escape(conv) + tm.group(3)
            return tm.group(0)

        return _X_TEXT.sub(on_t, si)

    return _X_SI.sub(on_si, xml), n[0]


_OFFICE_SPECS = {
    ".docx": (re.compile(r"word/(document|header\d*|footer\d*|footnotes|endnotes)\.xml$"),
              _W_RUN, _W_FONT, _W_TEXT, _W_RETAG, "w"),
    ".pptx": (re.compile(r"ppt/(slides|notesSlides)/[^/]+\.xml$"),
              _A_RUN, _A_FONT, _A_TEXT, _A_RETAG, "a"),
    ".xlsx": (re.compile(r"xl/sharedStrings\.xml$"),
              _X_RUN, _X_FONT, _X_TEXT, _X_RETAG, "x"),
}


def delegacify_office(src_path) -> tuple[bytes | None, int]:
    """Convert Bijoy/SutonnyMJ-font runs inside a .docx/.pptx/.xlsx to Unicode Bengali,
    in place in the OOXML (non-legacy runs untouched). Returns (new_bytes|None, runs_converted).
    Returns (None, 0) for non-Office files or when nothing legacy was found."""
    ext = os.path.splitext(str(src_path))[1].lower()
    spec = _OFFICE_SPECS.get(ext)
    if not spec:
        return None, 0
    part_re, run_re, font_re, text_re, retag_re, kind = spec
    total = 0
    try:
        with zipfile.ZipFile(src_path) as zin:
            edited: dict[str, str] = {}
            for name in zin.namelist():
                if not part_re.search(name):
                    continue
                try:
                    xml = zin.read(name).decode("utf-8")
                except (UnicodeDecodeError, KeyError):
                    continue
                new_xml, c = _delegacify_runs(xml, run_re, font_re, text_re, retag_re)
                if kind == "x":
                    new_xml, c2 = _delegacify_plain_xlsx(new_xml)
                    c += c2
                if c:
                    edited[name] = new_xml
                    total += c
            if not total:
                return None, 0
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zout:
                for item in zin.infolist():
                    if item.filename in edited:
                        zout.writestr(item, edited[item.filename].encode("utf-8"))
                    else:
                        zout.writestr(item, zin.read(item.filename))
            return buf.getvalue(), total
    except (zipfile.BadZipFile, OSError, KeyError):
        return None, 0


def delegacify_to_temp(src_path) -> tuple[str | None, int]:
    """If ``src_path`` is a legacy-font Office file, write a delegacified copy to a temp
    file and return (temp_path, runs_converted); else (None, 0). The caller converts the
    temp file (e.g. via MarkItDown) so structure/tables are preserved."""
    data, count = delegacify_office(src_path)
    if not data or not count:
        return None, 0
    fd, tmp = tempfile.mkstemp(suffix=os.path.splitext(str(src_path))[1].lower())
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    return tmp, count
