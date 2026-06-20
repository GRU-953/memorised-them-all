"""Token-free recall — return only a tiny, relevant slice of memory.

The query is ranked against the stored recall units (theme summaries + entity cards)
with model-free **BM25 lexical** scoring (script-agnostic, Bengali-aware), and the
top-k units are returned with provenance. Lexical overlap of the top hit gates a
low-confidence signal so off-topic queries stay declinable. Whole documents are never
returned — Claude gets a compact, citable slice, which is what keeps recall
near-zero-token. (A legacy hash-embedding store is still loaded for back-compat but is
not used for ranking.)

Every string field that recall/overview echo back is HARD-CAPPED in UTF-8 BYTES (not
characters) via ``_clip_bytes`` — a char slice silently leaks 3× the budget for 3-byte
Bengali, and the ``label`` field (which the Bengali entity path can grow without the
80-char Latin gate) is the one that must never be uncapped. This is the token-free
guarantee, enforced at the tool boundary regardless of what the store holds.
"""
from __future__ import annotations

import math
import re
import unicodedata

from . import locks
from .config import Config
from .store import load_graph, load_vectors

# Hard per-field caps, in UTF-8 BYTES, so a verbose (or prompt-injected / document-borne)
# field can never blow up Claude's context. These bound EVERY string recall/overview
# return — label, text, synopsis, theme summary, doc names — because the token-free
# guarantee is a byte guarantee, and Bengali is ~3 bytes/char.
_MAX_LABEL = 200       # entity/theme name — long values are junk; names fit easily
_MAX_HIT_TEXT = 600    # citable fact slice
_MAX_DOC_NAME = 160    # one provenance basename
_MAX_HIT_DOCS = 5
_MAX_SYNOPSIS = 1200   # deterministic fact-join synopsis recall/overview echo back


def _clip_bytes(s, max_bytes: int) -> str:
    """Truncate ``s`` to at most ``max_bytes`` UTF-8 bytes without splitting a multi-byte
    codepoint. The byte cap (not a char slice) is what actually enforces token-free for
    multi-byte scripts like Bengali."""
    s = s or ""
    b = s.encode("utf-8")
    if len(b) <= max_bytes:
        return s
    return b[:max_bytes].decode("utf-8", "ignore")


def _hit(u: dict, score) -> dict:
    docs = u.get("docs", []) or []
    out = {"score": score, "kind": u.get("kind"),
           "label": _clip_bytes(u.get("label"), _MAX_LABEL),
           "text": _clip_bytes(u.get("text"), _MAX_HIT_TEXT),
           "docs": [_clip_bytes(d, _MAX_DOC_NAME) for d in docs[:_MAX_HIT_DOCS]]}
    if len(docs) > _MAX_HIT_DOCS:
        out["doc_count"] = len(docs)
    return out


# Token = a run of Latin/digit word-chars OR Bengali-block chars. The explicit Bengali
# range (U+0980–U+09FF) is REQUIRED: bare \w SPLITS Bengali words at the halant (্,
# U+09CD) — e.g. "উত্তর"→["উত","তর"], "ব্র্যাক"→dropped fragments — which silently breaks
# Bengali recall. Keeping the whole block together tokenises Bengali words intact.
_TOK = re.compile(r"[\wঀ-৿]+", re.UNICODE)


def _tokens(s: str) -> list[str]:
    # NFC-normalise first so a Bengali word written with differently-composed/ordered
    # combining marks (query vs OCR/converted text) tokenises identically. len>1 keeps
    # Bengali words + multi-char English; drops single noise chars.
    s = unicodedata.normalize("NFC", s or "").lower()
    return [w for w in _TOK.findall(s) if len(w) > 1]


# Content-free words excluded from the off-topic OVERLAP guard so a single common-word
# coincidence ("best pizza" ↔ "Best Practices") can't keep an irrelevant hit confident.
# Reuses the extractor's English + Bengali stoplists + a tiny recall-local set. This only
# affects the advisory low_confidence flag — never BM25 ranking or scores.
from .extract import _BN_STOP as _EX_BN_STOP  # noqa: E402
from .extract import _STOPWORDS as _EX_STOP  # noqa: E402

_OVERLAP_STOP = frozenset(
    {w.lower() for w in _EX_STOP} | set(_EX_BN_STOP)
    | {"best", "recipe", "new", "total", "overall", "part", "using", "good", "report",
       "data", "information", "general", "various", "different", "make", "made"})


def _lexical_overlap(query: str, text: str) -> int:
    """# of distinct CONTENT words (len>1, non-stopword) shared by the query and a hit's
    text. Stopword-filtered so a lone common-word match (e.g. "best") doesn't read as
    topical overlap and wrongly keep an off-topic hit confident. FALLBACK: if the query is
    *entirely* common words (e.g. "data report information"), the filtered set is empty and
    every hit would read low-confidence even on a strong BM25 match — so fall back to the
    unfiltered token overlap, which still distinguishes a real topical hit from noise."""
    qt, tt = set(_tokens(query)), set(_tokens(text))
    q = qt - _OVERLAP_STOP
    if not q:                       # all query words are common → don't over-decline
        return len(qt & tt)
    return len(q & (tt - _OVERLAP_STOP))


def _bm25_rank(query: str, meta: list[dict], k: int) -> list[tuple[float, int]]:
    """Rank recall units by BM25 over (label + text). Model-free and script-agnostic
    (Unicode tokenisation → Bengali words match too), and far better than the
    deterministic hash-embedding cosine, which has no semantic OR lexical signal. Units
    that carry facts (longer text) naturally outrank bare-label entities. k1/b standard."""
    q_terms = set(_tokens(query))
    if not q_terms:
        return []
    k1, b = 1.5, 0.75
    docs = [_tokens((u.get("label", "") + " ") * 2 + (u.get("text") or "")) for u in meta]
    n = len(docs) or 1
    avgdl = (sum(len(d) for d in docs) / n) or 1.0
    df = dict.fromkeys(q_terms, 0)
    for d in docs:
        for t in q_terms.intersection(d):
            df[t] += 1
    idf = {t: math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5)) for t in q_terms}
    scored: list[tuple[float, int]] = []
    for i, d in enumerate(docs):
        dl = len(d)
        if not dl:
            continue
        tf: dict[str, int] = {}
        for w in d:
            if w in q_terms:
                tf[w] = tf.get(w, 0) + 1
        if not tf:
            continue
        s = sum(idf[t] * (f * (k1 + 1)) / (f + k1 * (1 - b + b * dl / avgdl))
                for t, f in tf.items())
        scored.append((s, i))
    scored.sort(key=lambda x: (-x[0], x[1]))   # deterministic tiebreak by index
    return scored[:k]


def recall(cfg: Config, query: str, k: int | None = None) -> dict:
    # Shared (multi-reader) lock: never observe a half-updated graph<->vectors
    # pair while a digest is persisting (LIFE-01).
    with locks.read_lock(cfg):
        return _recall_locked(cfg, query, k)


def _recall_locked(cfg: Config, query: str, k: int | None) -> dict:
    # Hard-clamp k so a caller can never pull the whole graph's text into Claude's
    # context — the token-free guarantee depends on recall returning a tiny slice.
    try:
        k = int(k or cfg.recall_k)
    except (TypeError, ValueError, OverflowError):
        k = cfg.recall_k
    k = max(1, min(k, 50))
    loaded = load_vectors(cfg)
    if loaded is None:
        return {"status": "no_memory", "project": cfg.project,
                "message": "Nothing digested for this project yet."}
    _matrix, meta = loaded     # vectors retained for compat; ranking is now BM25 lexical

    # BM25 lexical ranking over the recall units (entity cards + theme summaries).
    # Model-free, script-agnostic (matches Bengali too), and ranks by genuine relevance
    # — unlike the hash-embedding cosine, which had neither semantic nor lexical signal.
    ranked = _bm25_rank(query, meta, k)
    hits = [_hit(meta[i], round(float(s), 3)) for s, i in ranked if i < len(meta)]
    raw_top = hits[0]["score"] if hits else 0.0   # best score BEFORE the floor
    # Optional absolute score floor (MTA_RECALL_MIN_SCORE; 0 = off, the default). Now on
    # the BM25 scale (unbounded positive) rather than the old 0–1 cosine scale.
    if cfg.recall_min_score > 0:
        hits = [h for h in hits if h["score"] >= cfg.recall_min_score]
    # Off-topic guard: no BM25 overlap at all ⇒ low confidence (Claude can decline).
    low_conf = (not hits) or _lexical_overlap(query, hits[0].get("label", "") + " "
                                              + hits[0].get("text", "")) == 0
    doc = load_graph(cfg)
    return {"status": "ok", "project": cfg.project, "query": query,
            "synopsis": _clip_bytes((doc or {}).get("synopsis", ""), _MAX_SYNOPSIS),
            # The mode this memory was last BUILT in (always "deterministic" in v2).
            "memory_mode": (doc or {}).get("stats", {}).get("mode"),
            "top_score": (hits[0]["score"] if hits else 0.0),
            "raw_top_score": raw_top, "low_confidence": low_conf, "hits": hits}


def _lexical(query: str, meta: list[dict], k: int, cfg: Config) -> dict:
    """Legacy whole-word-overlap fallback, retained for back-compat (the main path is
    BM25). It keeps the SAME relevance contract so an off-topic query stays declinable
    (DOC-01): `low_confidence`, `top_score`, `raw_top_score`, and a (capped) `synopsis`
    are all present."""
    q = set(query.lower().split())
    scored = []
    for u in meta:
        words = set((u.get("text") or "").lower().split())
        overlap = len(q & words)
        if overlap:
            scored.append((overlap, u))
    scored.sort(key=lambda x: -x[0])
    hits = [_hit(u, s) for s, u in scored[:k]]
    top = hits[0]["score"] if hits else 0   # integer lexical-overlap scale (mode=lexical)
    doc = load_graph(cfg)
    return {"status": "ok", "project": cfg.project, "query": query, "mode": "lexical",
            "synopsis": _clip_bytes((doc or {}).get("synopsis", ""), _MAX_SYNOPSIS),
            "memory_mode": (doc or {}).get("stats", {}).get("mode"),
            "top_score": top, "raw_top_score": top,
            "low_confidence": not hits, "hits": hits}


def overview(cfg: Config) -> dict:
    with locks.read_lock(cfg):
        doc = load_graph(cfg)
    if not doc:
        return {"status": "no_memory", "project": cfg.project}
    return {"status": "ok", "project": cfg.project,
            "synopsis": _clip_bytes(doc.get("synopsis", ""), _MAX_SYNOPSIS),
            "stats": doc.get("stats", {}),
            "themes": [{"label": _clip_bytes(c.get("label"), _MAX_LABEL),
                        "summary": _clip_bytes(c.get("summary"), _MAX_HIT_TEXT)}
                       for c in doc.get("communities", [])][:20]}
