"""Knowledge extraction — entities, typed relations, and atomic facts per chunk.

Deterministic, dependency-free, classical-only. A capitalised noun-phrase + acronym
detector finds entities (gated to drop junk), same-sentence co-occurrence yields
relations, and entity-bearing sentences become facts. There is no LLM and no network:
the same chunk always yields the same extraction. Every emitted string is scrubbed of
control / fence tokens so injected documents can't poison memory.md or recall.

Output feeds the local graph builder only and never returns document text to Claude.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .segment import Chunk

_ENTITY_RE = re.compile(
    r"\b([A-Z][a-zA-Z0-9]+(?:\s+[A-Z][a-zA-Z0-9]+){0,3}|[A-Z]{2,6})\b")
# Bengali (U+0980–U+09FF) proper-noun candidates: runs of 1–4 Bengali "words". Bengali
# has no capitalisation, so we can't use case as the proper-noun signal — instead we
# take multi-word Bengali phrases (and recurring single words), strip edge particles,
# and let salience/community detection surface the real names/orgs/places. Noisier than
# the English path, but it means a Bengali-heavy corpus (UPGP) is no longer invisible.
_BN = r"ঀ-৿"
_BN_WORD = rf"[{_BN}]+"
_BN_RE = re.compile(rf"((?:{_BN_WORD})(?:\s+{_BN_WORD}){{0,3}})")
# Common Bengali function words / particles that must not start or end an entity (or
# stand alone). Small, high-frequency closed-class set — safe to strip.
_BN_STOP = {
    "এবং", "ও", "বা", "এই", "সেই", "যে", "যা", "তার", "তাদের", "এর", "ের", "টি", "টা",
    "করা", "করে", "করেন", "হয়", "হয়েছে", "হবে", "ছিল", "জন", "জনের", "থেকে", "জন্য",
    "সাথে", "মধ্যে", "কাছে", "পর", "আগে", "কিন্তু", "তবে", "যদি", "নয়", "না", "কে",
    "একটি", "একটা", "অংশগ্রহণকারী", "প্রধান", "মোঃ", "মোছাঃ", "জনাব",
}
_STOPWORDS = {
    "The", "This", "That", "These", "Those", "It", "We", "You", "They", "He",
    "She", "I", "A", "An", "And", "But", "Or", "If", "For", "In", "On", "At",
    "To", "Of", "As", "By", "Is", "Are", "Was", "Were", "Be", "Section",
    "Figure", "Table", "Chapter", "Note", "Page", "However", "Therefore",
    # Honorifics (kept out so "Dr. Lena Marsh" → "Lena Marsh", not "Dr"). Md/Mohd/Engr
    # cover the Bangladeshi NGO corpus's common name prefixes.
    "Dr", "Mr", "Mrs", "Ms", "Prof", "Sir", "Mx", "St", "Md", "Mohd", "Mohammad",
    "Mohammed", "Muhammad", "Engr", "Eng", "Adv", "Begum",
    # Common sentence-initial / imperative words that masquerade as single-token entities.
    "Ignore", "New", "Normal", "Please", "See", "Using", "Based", "Following", "Given",
    "Each", "Both", "All", "Some", "Many", "Most", "Such", "Other", "Overall", "Total",
    # Months & weekdays are rarely useful standalone entities.
    "January", "February", "March", "April", "May", "June", "July", "August",
    "September", "October", "November", "December", "Monday", "Tuesday",
    "Wednesday", "Thursday", "Friday", "Saturday", "Sunday", "Meeting",
}
# Suffix/keyword heuristics for lightweight entity typing (deterministic, no model).
_ORG_HINTS = ("Authority", "Programme", "Program", "Foundation", "Association",
              "Ministry", "Department", "Bank", "University", "College", "School",
              "Institute", "Committee", "Council", "Commission", "Corporation",
              "Company", "Ltd", "Inc", "Corp", "Co", "Network", "Unit", "Office",
              "Agency", "Society", "Federation", "Union", "Group", "Limited")
_PLACE_HINTS = ("District", "Division", "Upazila", "Union", "Village", "City",
                "Town", "Region", "Zone", "Sub-district", "Thana", "Ward")
# Static Bangladesh gazetteer (8 divisions + 64 districts, with common transliteration
# variants) + a few corpus-salient orgs. Deterministic literal sets → byte-identical
# output preserved. The corpus is organised BY district, so without this almost every
# place name ("Dhaka", "Barishal", "Rangpur") is typed "other" (was 96.5% "other").
_BD_PLACES = frozenset({
    # divisions
    "Dhaka", "Chattogram", "Chittagong", "Rajshahi", "Khulna", "Barishal", "Barisal",
    "Sylhet", "Rangpur", "Mymensingh",
    # districts (+ variants)
    "Comilla", "Cumilla", "Feni", "Brahmanbaria", "Rangamati", "Noakhali", "Chandpur",
    "Lakshmipur", "Laxmipur", "Coxsbazar", "Khagrachhari", "Bandarban", "Narsingdi",
    "Gazipur", "Narayanganj", "Tangail", "Kishoreganj", "Kishoregonj", "Manikganj",
    "Munshiganj", "Rajbari", "Madaripur", "Gopalganj", "Faridpur", "Shariatpur",
    "Sirajganj", "Sirajgonj", "Pabna", "Bogura", "Bogra", "Natore", "Joypurhat",
    "Chapainawabganj", "Naogaon", "Jashore", "Jessore", "Satkhira", "Meherpur",
    "Narail", "Chuadanga", "Kushtia", "Magura", "Bagerhat", "Jhenaidah", "Jhenidah",
    "Barguna", "Bhola", "Jhalokathi", "Jhalakathi", "Patuakhali", "Pirojpur",
    "Sunamganj", "Sunamgonj", "Habiganj", "Habigonj", "Moulvibazar", "Maulvibazar",
    "Panchagarh", "Dinajpur", "Lalmonirhat", "Nilphamari", "Gaibandha", "Thakurgaon",
    "Kurigram", "Jamalpur", "Sherpur", "Netrokona", "Netrakona",
})
# Corpus-salient organisations that carry no _ORG_HINTS suffix (so only a name list can
# type them). BRAC and its programme/research arms.
_KNOWN_ORGS = frozenset({
    "BRAC", "UPGP", "DIUPG", "BIGD", "VSSC", "CFPR", "BIDS",
})
# Spreadsheet/survey cell VALUES — high-frequency in beneficiary-data dumps but useless
# as standalone entities. Without this, a corpus of survey .xlsx makes "Male"/"No"/
# "Husband"/"Rural"/"NaN" the top entities, burying the real programme entities.
_VALUE_STOP = {
    "Male", "Female", "Yes", "No", "Na", "Nan", "None", "Null", "Other", "Others",
    "Husband", "Wife", "Son", "Daughter", "Father", "Mother", "Brother", "Sister",
    "Self", "Head", "Spouse", "Child", "Children", "Family", "Member",
    "Rural", "Urban", "Married", "Unmarried", "Single", "Widow", "Widowed", "Divorced",
    "Primary", "Secondary", "Illiterate", "Literate", "Muslim", "Hindu", "Christian",
    "True", "False", "High", "Low", "Medium", "Good", "Poor", "Average", "Total",
    "Name", "Age", "Sex", "Gender", "Address", "Phone", "Mobile", "Date", "Status",
    "Type", "Category", "Amount", "Number", "Count", "Code", "Id", "Sl", "Serial",
    "Nan", "NaN", "Na", "N/A", "Nil", "Tk", "Taka", "Pcs", "Kg", "Hh",
    # "Unnamed" is pandas/openpyxl's placeholder for an empty spreadsheet-column header
    # ("Unnamed: 0", "Unnamed: 3"); a corpus of survey .xlsx makes it a top entity.
    "Unnamed",
}
# Case-insensitive membership: spreadsheet exports vary the casing ("NaN"/"NAN"/"nan",
# "No"/"NO"). Compare lower-cased so a single styling variant can't slip through.
_VALUE_STOP_LC = frozenset(v.lower() for v in _VALUE_STOP)
_SENT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])|(?<=[।。！？])\s*")

# Strip a leading determiner so "The Nordic Grid Authority" resolves to the same node
# as "Nordic Grid Authority" (PIPE-06).
_LEADING_DET = {"The", "A", "An", "This", "That", "These", "Those"}

# Don't break a sentence right after these abbreviations ("… is Dr. Lena Marsh.").
_ABBREV = ("Dr", "Mr", "Mrs", "Ms", "Prof", "Sr", "Jr", "St", "Inc", "Ltd", "Co",
           "Corp", "vs", "etc", "No", "Fig", "Eq", "Vol", "Rev", "Gen", "Sen", "Rep")
_ABBREV_RE = re.compile(r"\b(" + "|".join(_ABBREV) + r")\.")


def _split_sentences(text: str) -> list[str]:
    """Split into sentences, but never right after a known abbreviation."""
    masked = _ABBREV_RE.sub(lambda m: m.group(1) + "\x00", text)  # mask the trailing dot
    return [p.replace("\x00", ".") for p in _SENT_RE.split(masked)]


@dataclass
class Extraction:
    entities: list[dict] = field(default_factory=list)   # {name,type}
    relations: list[dict] = field(default_factory=list)  # {source,relation,target}
    facts: list[str] = field(default_factory=list)


def _infer_type(name: str, text: str) -> str:
    """Best-effort entity type (person | org | place | other) from deterministic cues."""
    if any("ঀ" <= ch <= "৿" for ch in name):
        return "other"                                  # Bengali: no cheap sub-typing
    words = name.split()
    # Static gazetteer first — high-precision, deterministic. A district organised-by
    # corpus would otherwise type its places as "other".
    if name in _BD_PLACES:
        return "place"
    if name in _KNOWN_ORGS:
        return "org"
    if re.search(r"\b(?:Dr|Mr|Mrs|Ms|Md|Mohd|Mohammad|Mohammed|Muhammad|Prof|Engr|Eng|"
                 r"Adv|Begum)\.?\s+" + re.escape(name), text):
        return "person"
    if any(w in _ORG_HINTS for w in words):
        return "org"
    if any(w in _PLACE_HINTS for w in words):
        return "place"
    return "other"


_BN_DIGITS = "০১২৩৪৫৬৭৮৯"

# Long digit-runs = phone/NID/account numbers (Latin OR Bengali numerals). Used to keep
# beneficiary PII out of facts/summaries and to redact any that slips through.
_PII_DIGITS_RE = re.compile(r"\d{6,}|[" + _BN_DIGITS + r"]{6,}")
# pandas/openpyxl empty-header placeholder, any styling ("Unnamed", "Unnamed: 3",
# "Unnamed12"). A leading "Unnamed" is never a real proper-noun in this domain.
_UNNAMED_RE = re.compile(r"(?i)^Unnamed")


def _is_tabular_or_pii(s: str) -> bool:
    """Deterministic guard: True for spreadsheet rows / beneficiary rosters that must not
    become facts or theme summaries. Catches pipe-delimited rows and any string carrying a
    long digit-run (phone/ID, Latin or Bengali numerals). Pure string/regex, no model."""
    if s.count("|") >= 3:
        return True
    if _PII_DIGITS_RE.search(s):
        return True
    if s.count("|") >= 2:                       # short-cell row, e.g. "Male | No | Rural"
        cells = [c.strip() for c in s.split("|")]
        if sum(1 for c in cells if 0 < len(c.split()) <= 3) >= 3:
            return True
    return False


def _redact_pii(s: str) -> str:
    """Collapse long digit-runs (phone/ID numbers; Latin or Bengali numerals) to a
    placeholder so a stray contact number can never persist verbatim in a fact/summary.
    Applied ONLY to facts/summaries — never to entity-label matching."""
    return _PII_DIGITS_RE.sub("[number]", s or "")


def _bn_candidate(raw: str) -> str | None:
    """Trim edge particles + Bengali numerals from a Bengali phrase; None if nothing
    meaningful remains (so '১২৪০' counts and 'ভোলা জেলায় ১২৪০' → 'ভোলা জেলায়')."""
    toks = [t for t in raw.split() if t and not all(ch in _BN_DIGITS for ch in t)]
    while toks and toks[0] in _BN_STOP:
        toks = toks[1:]
    while toks and toks[-1] in _BN_STOP:
        toks = toks[:-1]
    if not toks or all(t in _BN_STOP for t in toks):
        return None
    name = " ".join(toks)
    return name if len(name) >= 3 else None


def _classical(chunk: Chunk) -> Extraction:
    """Dependency-free extraction — the ONLY path in v2, so quality matters. Capitalised
    (Latin) AND Bengali-script phrase entities (gated to drop junk: sentence-initial lone
    words and fence/control tokens are removed), lightweight person/org/place typing,
    same-sentence relations, and entity-bearing facts. Fully deterministic."""
    # Neutralise fence delimiters + control tokens BEFORE extraction so a document can't
    # plant "<<<END>>>" / "<tool_call>" as entities or facts (defence-in-depth; there's
    # no LLM to hijack, but it keeps memory.md clean). Also repair vetted artifact-only
    # Bengali reorder mojibake (e.g. গ্রম্নপ→গ্রুপ) so entities/facts/recall use the correct
    # word — a graph rebuild cleans an existing memory without re-conversion.
    from .bangla_legacy import normalize_reorder_artifacts
    text = normalize_reorder_artifacts(_defang_fence(_scrub(chunk.text)))
    sentences = [re.sub(r"\s+", " ", s).strip() for s in _split_sentences(text)]
    counts: dict[str, int] = {}
    provisional: set[str] = set()   # single lone-word entities → keep only if they recur

    for m in _ENTITY_RE.finditer(text):
        # Collapse internal whitespace/newlines so a label spanning a line break
        # (e.g. table cells) becomes "Lena Marsh", not "Lena\nMarsh".
        name = re.sub(r"\s+", " ", m.group(1)).strip()
        # Strip a leading determiner / honorific so "The Nordic Grid Authority" and
        # "Md Karim Rahman" resolve to "Nordic Grid Authority" / "Karim Rahman".
        for _ in range(2):
            head, _, rest = name.partition(" ")
            if rest and (head in _LEADING_DET or head in _STOPWORDS):
                name = rest
        if len(name) < 2 or not _valid_entity(name):
            continue
        # Drop the pandas/openpyxl "Unnamed[: N]" empty-column placeholder regardless of
        # tokenisation ("Unnamed", "Unnamed3").
        if _UNNAMED_RE.match(name):
            continue
        # Drop names made ENTIRELY of stop / survey-value words — single tokens
        # ("NaN"/"Male") and table-cell runs ("Name NaN NAN", "No Total Tk").
        if all(t in _STOPWORDS or t.lower() in _VALUE_STOP_LC for t in name.split()):
            continue
        if " " not in name and not name.isupper():
            provisional.add(name)        # lone mixed-case word (often sentence-initial junk)
        counts[name] = counts.get(name, 0) + 1

    for m in _BN_RE.finditer(text):
        name = _bn_candidate(m.group(1))
        if not name:
            continue
        if " " not in name:
            provisional.add(name)        # lone Bengali word → keep only if it recurs
        counts[name] = counts.get(name, 0) + 1

    # Drop lone single-occurrence words (sentence-initial junk, incidental words); keep
    # multi-word names, ALL-CAPS acronyms, and anything that appears more than once.
    for n in [k for k in counts if k in provisional and counts[k] < 2]:
        del counts[n]

    # Keep the most salient entities in the chunk.
    ents = sorted(counts, key=lambda n: (-counts[n], n))[:8]
    entities = [{"name": _scrub(n), "type": _infer_type(n, text)} for n in ents if _scrub(n)]

    # Relations: co-occurrence WITHIN A SENTENCE only (was a chunk-wide clique → mostly
    # meaningless O(n²) edges that diluted community detection). De-duplicated.
    relations: list[dict] = []
    seen_rel: set[tuple[str, str]] = set()
    for s in sentences:
        present = [e for e in ents if e in s]
        for i in range(len(present)):
            for j in range(i + 1, len(present)):
                key = (present[i], present[j])
                if key not in seen_rel:
                    seen_rel.add(key)
                    relations.append({"source": _scrub(present[i]), "relation": "related_to",
                                      "target": _scrub(present[j])})
    # Facts: prefer sentences that actually mention a kept entity (more useful for recall);
    # fall back to any sentence if none qualify. Abbreviation-aware split, scrubbed.
    facts: list[str] = []
    for grounded in (True, False):
        for s in sentences:
            # Never let a spreadsheet row / beneficiary roster (names+ages+phone numbers)
            # become a fact — privacy + noise. Redact any stray long digit-run as a
            # belt-and-suspenders before storing.
            if (20 <= len(s) <= 240 and not _is_tabular_or_pii(s)
                    and (not grounded or any(e in s for e in ents))):
                f = _redact_pii(_scrub(s))
                if f and f not in facts:
                    facts.append(f)
            if len(facts) >= 6:
                break
        if facts:
            break
    return Extraction(entities=entities, relations=relations, facts=facts)


# Chat/tool control tokens a chat-tuned model can emit mid-output (qwen3 <tool_call>,
# ChatML <|im_start|>, gemma <start_of_turn>, DeepSeek fullwidth <｜…｜>, …) must never
# reach an entity/fact/summary (it pollutes memory.md + recall, and is a mild injection
# vector to Claude). Case-insensitive; the pipe arm allows the fullwidth ｜ (U+FF5C).
_SPECIAL_TOK = re.compile(
    r"<[\|｜][^>]{0,80}?[\|｜]>"
    r"|</?\s*(?:tool_call|tool_response|think|thinking|im_start|im_end|"
    r"start_of_turn|end_of_turn|start_header_id|end_header_id|eot_id)\s*>",
    re.IGNORECASE)

# Prompt-fence delimiters wrapping document data. Document text must NOT be able to forge
# them (second-order prompt injection), so we neutralise any occurrence inside the data.
_FENCE_TOK = re.compile(r"<<<\s*(?:DATA|CHUNK|END)\s*>>>", re.IGNORECASE)


def _scrub(s: str) -> str:
    s = s or ""
    for _ in range(5):  # fixed-point: a single pass lets "<tool_<tool_call>call>" re-form
        new = _SPECIAL_TOK.sub("", s)
        if new == s:
            break
        s = new
    return re.sub(r"\s{2,}", " ", s).strip()


def _defang_fence(s: str) -> str:
    """Make the <<<DATA>>>/<<<CHUNK>>>/<<<END>>> fence un-forgeable from inside data."""
    return _FENCE_TOK.sub("[delim]", s or "")


# Long hex / binary blobs (embedded colour profiles, XMP, base16 dumps from design files):
# "FF3300FF3333…", "B8B7B6B5…". Never a real entity.
_HEXBLOB_RE = re.compile(r"(?i)^[0-9A-F]{12,}$")


def _valid_entity(name: str) -> bool:
    """Reject obvious non-entities a model or the regex can emit: sentence-length blobs,
    URLs, pure numbers/punctuation, multi-line strings, and hex/binary dumps."""
    if not name or len(name) > 80 or len(name.split()) > 8 or "\n" in name or "://" in name:
        return False
    if " " not in name:
        # A long single token that is all hex, or has no vowel at all, is a binary/code
        # dump (colour profile, base16, identifier soup), not a name.
        if _HEXBLOB_RE.match(name):
            return False
        if len(name) > 24 and not re.search(r"[aeiouAEIOU]", name):
            return False
    return re.search(r"[^\W\d_]", name) is not None  # must contain at least one letter


def extract_chunk(chunk: Chunk) -> Extraction:
    return _classical(chunk)
