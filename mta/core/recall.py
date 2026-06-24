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
from .store import load_bm25_index, load_graph, load_meta

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
    multi-byte scripts like Bengali. Total by construction — coerces a non-str field (e.g.
    a hand-corrupted graph.json) to str and treats a non-positive cap as empty, so a tool
    handler (e.g. the un-wrapped memory_overview) can never raise crossing this boundary."""
    if not isinstance(s, str):
        s = "" if s is None else str(s)
    if max_bytes <= 0:
        return ""
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


def _unit_doc_tokens(u: dict) -> list[str]:
    """The BM25 'document' token list for one recall unit — label weighted ×2, then text.
    The SINGLE source of truth for unit tokenisation: the digest-time cache builder and
    the on-the-fly fallback both call this, so a cached index can never tokenise
    differently from a live re-tokenisation (R-13 equivalence)."""
    return _tokens((u.get("label", "") + " ") * 2 + (u.get("text") or ""))


def _bm25_rank_tokenized(q_terms: set[str], docs: list[list[str]], k: int) -> list[tuple[float, int]]:
    """BM25 core over PRE-TOKENISED docs (the exact loop formerly inline in `_bm25_rank`).
    Identical math/output whether `docs` came from the persisted cache or live
    tokenisation — `docs[i]` corresponds 1:1 to recall-unit `i`."""
    if not q_terms:
        return []
    k1, b = 1.5, 0.75
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


def _bm25_rank(query: str, meta: list[dict], k: int) -> list[tuple[float, int]]:
    """Rank recall units by BM25 over (label + text), tokenising on the fly. Model-free
    and script-agnostic (Bengali words match too). The on-the-fly fallback for when no
    persisted index is present; kept as the reference path (and public signature)."""
    return _bm25_rank_tokenized(set(_tokens(query)),
                                [_unit_doc_tokens(u) for u in meta], k)


def _bm25_rank_cached(query: str, meta: list[dict], cache: dict | None,
                      k: int) -> list[tuple[float, int]]:
    """Rank using the persisted pre-tokenised index when it is present AND structurally
    valid (a list of token-lists, one per recall unit); otherwise tokenise on the fly.
    The length-match gate mirrors the torn-store discipline — a stale/garbage cache can
    never mis-rank, only fall back. Output is byte-identical to ``_bm25_rank`` because
    the cached tokens were produced by the same ``_unit_doc_tokens`` at digest time."""
    docs = None
    if isinstance(cache, dict):
        c_docs = cache.get("docs")
        if (isinstance(c_docs, list) and len(c_docs) == len(meta)
                and all(isinstance(d, list) and all(isinstance(t, str) for t in d)
                        for d in c_docs)):
            docs = c_docs
    if docs is None:
        docs = [_unit_doc_tokens(u) for u in meta]
    return _bm25_rank_tokenized(set(_tokens(query)), docs, k)


def _unit_matches(u: dict, doc: str | None, entity_type: str | None) -> bool:
    """Structured recall filters (v3.1, WP-130), applied AFTER BM25 ranking so relevance
    order is preserved within the filtered set. `doc` keeps units whose provenance includes
    that source (matched by basename, case-insensitive — theme units carry no docs, so a
    doc filter naturally narrows to cited entity facts). `entity_type` keeps only entity
    units of that type (needs the v3.1 `type` field → re-digest an old store to use it)."""
    if doc:
        from pathlib import Path
        want = Path(doc.strip()).name.lower()
        if not any(Path(str(d)).name.lower() == want for d in (u.get("docs") or [])):
            return False
    if entity_type:
        if u.get("kind") != "entity" or str(u.get("type", "")).lower() != entity_type.strip().lower():
            return False
    return True


def recall(cfg: Config, query: str, k: int | None = None, *,
           projects: list[str] | None = None, doc: str | None = None,
           entity_type: str | None = None) -> dict:
    # `projects` (v3.1, WP-144) federates recall across several memories; otherwise the
    # active project under a shared (multi-reader) lock — never observe a half-updated
    # graph<->vectors pair while a digest is persisting (LIFE-01).
    if projects:
        return _recall_federated(cfg, query, k, projects, doc, entity_type)
    with locks.read_lock(cfg):
        return _recall_locked(cfg, query, k, doc=doc, entity_type=entity_type)


def _recall_locked(cfg: Config, query: str, k: int | None, *,
                   doc: str | None = None, entity_type: str | None = None) -> dict:
    # Hard-clamp k so a caller can never pull the whole graph's text into Claude's
    # context — the token-free guarantee depends on recall returning a tiny slice.
    try:
        k = int(k or cfg.recall_k)
    except (TypeError, ValueError, OverflowError):
        k = cfg.recall_k
    k = max(1, min(k, 50))
    meta = load_meta(cfg)      # R-15: meta only — BM25 never reads the embedding matrix
    if meta is None:
        return {"status": "no_memory", "project": cfg.project,
                "message": "Nothing digested for this project yet."}

    # BM25 lexical ranking over the recall units (entity cards + theme summaries).
    # Model-free, script-agnostic (matches Bengali too), and ranks by genuine relevance.
    # R-13: use the digest-time pre-tokenised index when present; fall back to on-the-fly.
    # With a structured filter active, rank the FULL set first (not just top-k) so the
    # filter can't starve the result of matching-but-lower-ranked units.
    filtering = bool(doc or entity_type)
    ranked = _bm25_rank_cached(query, meta, load_bm25_index(cfg), len(meta) if filtering else k)
    hits = []
    for s, i in ranked:
        if i >= len(meta):
            continue
        if filtering and not _unit_matches(meta[i], doc, entity_type):
            continue
        hits.append(_hit(meta[i], round(float(s), 3)))
        if len(hits) >= k:
            break
    raw_top = hits[0]["score"] if hits else 0.0   # best score BEFORE the floor
    # Optional absolute score floor (MTA_RECALL_MIN_SCORE; 0 = off, the default). Now on
    # the BM25 scale (unbounded positive) rather than the old 0–1 cosine scale.
    if cfg.recall_min_score > 0:
        hits = [h for h in hits if h["score"] >= cfg.recall_min_score]
    # Off-topic guard: no BM25 overlap at all ⇒ low confidence (Claude can decline).
    low_conf = (not hits) or _lexical_overlap(query, hits[0].get("label", "") + " "
                                              + hits[0].get("text", "")) == 0
    graph = load_graph(cfg)
    out = {"status": "ok", "project": cfg.project, "query": query,
           "synopsis": _clip_bytes((graph or {}).get("synopsis", ""), _MAX_SYNOPSIS),
           # The mode this memory was last BUILT in (always "deterministic" in v2).
           "memory_mode": (graph or {}).get("stats", {}).get("mode"),
           "top_score": (hits[0]["score"] if hits else 0.0),
           "raw_top_score": raw_top, "low_confidence": low_conf, "hits": hits}
    if filtering:
        out["filters"] = {k2: v for k2, v in (("doc", doc), ("entity_type", entity_type)) if v}
    return out


def _recall_federated(cfg: Config, query: str, k: int | None,
                      projects: list[str], doc: str | None, entity_type: str | None) -> dict:
    """Multi-project recall (v3.1, WP-144): rank each named project independently, tag every
    hit with its project, then merge by score and cap to k — so one question can draw cited
    slices from several memories at once. Still token-free (the same per-field byte caps and
    k clamp apply to the merged result). Read-only; each project is read under its own shared
    lock. Cross-corpus BM25 scores aren't perfectly comparable (different idf/avg-length), so
    the merge is a best-effort federation, not a single global ranking."""
    import dataclasses

    try:
        k = int(k or cfg.recall_k)
    except (TypeError, ValueError, OverflowError):
        k = cfg.recall_k
    k = max(1, min(k, 50))

    names: list[str] = []
    seen: set[str] = set()
    for p in projects:
        if not isinstance(p, str) or not p.strip():
            continue
        pcfg = dataclasses.replace(cfg).with_project(p)
        if pcfg.project in seen:
            continue
        seen.add(pcfg.project)
        names.append(pcfg.project)

    all_hits: list[dict] = []
    for name in names:
        pcfg = dataclasses.replace(cfg).with_project(name)
        with locks.read_lock(pcfg):
            res = _recall_locked(pcfg, query, k, doc=doc, entity_type=entity_type)
        if res.get("status") != "ok":
            continue
        for h in res.get("hits", []):
            h = dict(h)
            h["project"] = name
            all_hits.append(h)
    all_hits.sort(key=lambda h: -h["score"])
    all_hits = all_hits[:k]
    low_conf = (not all_hits) or _lexical_overlap(
        query, all_hits[0].get("label", "") + " " + all_hits[0].get("text", "")) == 0
    out = {"status": "ok", "query": query, "projects": names, "federated": True,
           "top_score": all_hits[0]["score"] if all_hits else 0.0,
           "low_confidence": low_conf, "hits": all_hits}
    if doc or entity_type:
        out["filters"] = {k2: v for k2, v in (("doc", doc), ("entity_type", entity_type)) if v}
    return out


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
