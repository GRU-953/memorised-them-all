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
_STOPWORDS = {
    "The", "This", "That", "These", "Those", "It", "We", "You", "They", "He",
    "She", "I", "A", "An", "And", "But", "Or", "If", "For", "In", "On", "At",
    "To", "Of", "As", "By", "Is", "Are", "Was", "Were", "Be", "Section",
    "Figure", "Table", "Chapter", "Note", "Page", "However", "Therefore",
    # Honorifics (kept out so "Dr. Lena Marsh" → "Lena Marsh", not "Dr").
    "Dr", "Mr", "Mrs", "Ms", "Prof", "Sir", "Mx", "St",
    # Months & weekdays are rarely useful standalone entities.
    "January", "February", "March", "April", "May", "June", "July", "August",
    "September", "October", "November", "December", "Monday", "Tuesday",
    "Wednesday", "Thursday", "Friday", "Saturday", "Sunday", "Meeting",
}
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


def _classical(chunk: Chunk) -> Extraction:
    """Dependency-free extraction — the DEFAULT path on the micro/4 GB profile, so quality
    matters. Capitalised-phrase entities (gated to drop junk), relations scoped to
    same-SENTENCE co-occurrence (not a chunk-wide O(n²) clique), and entity-bearing facts.
    Every string is scrubbed of control/fence tokens so injected docs can't poison memory."""
    text = chunk.text
    sentences = [re.sub(r"\s+", " ", s).strip() for s in _split_sentences(text)]
    counts: dict[str, int] = {}
    for m in _ENTITY_RE.finditer(text):
        # Collapse internal whitespace/newlines so a label spanning a line break
        # (e.g. table cells) becomes "Lena Marsh", not "Lena\nMarsh".
        name = re.sub(r"\s+", " ", m.group(1)).strip()
        # Strip a leading determiner so "The Nordic Grid Authority" counts as
        # "Nordic Grid Authority" (PIPE-06).
        head, _, rest = name.partition(" ")
        if rest and head in _LEADING_DET:
            name = rest
        if name in _STOPWORDS or len(name) < 2 or not _valid_entity(name):
            continue
        counts[name] = counts.get(name, 0) + 1
    # Keep the most salient entities in the chunk.
    ents = sorted(counts, key=lambda n: (-counts[n], n))[:8]
    entities = [{"name": _scrub(n), "type": "other"} for n in ents if _scrub(n)]

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
            if 20 <= len(s) <= 240 and (not grounded or any(e in s for e in ents)):
                f = _scrub(s)
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


def _valid_entity(name: str) -> bool:
    """Reject obvious non-entities a model or the regex can emit: sentence-length blobs,
    URLs, pure numbers/punctuation, multi-line strings."""
    if not name or len(name) > 80 or len(name.split()) > 8 or "\n" in name or "://" in name:
        return False
    return re.search(r"[^\W\d_]", name) is not None  # must contain at least one letter


def extract_chunk(chunk: Chunk) -> Extraction:
    return _classical(chunk)
