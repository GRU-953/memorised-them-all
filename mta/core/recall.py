"""Token-free recall — return only a tiny, relevant slice of memory.

The query is embedded with the same local model used at digest time, scored by
cosine against the stored recall units (theme summaries + entity cards), and the
top-k units are returned with provenance. Whole documents are never returned —
Claude gets a compact, citable slice, which is what keeps recall near-zero-token.
"""
from __future__ import annotations

import re

import numpy as np

from . import locks
from .config import Config
from .embed import Embedder, cosine
from .lifecycle import OllamaManager
from .store import load_graph, load_vectors

# Hard per-hit caps so a verbose (or prompt-injected) local-model summary can
# never blow up Claude's context — the token-free guarantee must hold on the
# accurate path, not just the classical one.
_MAX_HIT_TEXT = 600
_MAX_HIT_DOCS = 5
# The synopsis is an LLM-generated summary that recall/overview echo back, so bound
# it too — the token-free guarantee must cap every field that can grow with input.
_MAX_SYNOPSIS = 1200


def _hit(u: dict, score) -> dict:
    docs = u.get("docs", []) or []
    out = {"score": score, "kind": u.get("kind"), "label": u.get("label"),
           "text": (u.get("text") or "")[:_MAX_HIT_TEXT], "docs": docs[:_MAX_HIT_DOCS]}
    if len(docs) > _MAX_HIT_DOCS:
        out["doc_count"] = len(docs)
    return out


def _lexical_overlap(query: str, text: str) -> int:
    """# of distinct content words (len>2) shared by the query and a hit's text — a
    model-free relevance signal for the offline/hashing recall path (DOC-01)."""
    q = {w for w in re.findall(r"\w+", (query or "").lower()) if len(w) > 2}
    t = set(re.findall(r"\w+", (text or "").lower()))
    return len(q & t)


def recall(cfg: Config, query: str, k: int | None = None,
           ollama: OllamaManager | None = None) -> dict:
    # Shared (multi-reader) lock: never observe a half-updated graph<->vectors
    # pair while a digest is persisting (LIFE-01).
    with locks.read_lock(cfg):
        return _recall_locked(cfg, query, k, ollama)


def _recall_locked(cfg: Config, query: str, k: int | None,
                   ollama: OllamaManager | None) -> dict:
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
    matrix, meta = loaded
    ollama = ollama or OllamaManager(cfg)
    embedder = Embedder(cfg, ollama)
    qv = embedder.embed([query], kind="query")
    if qv.shape[1] != matrix.shape[1]:
        # Embedding backend changed since digest; degrade to lexical overlap.
        return _lexical(query, meta, k, cfg)

    scores = cosine(qv, matrix)[0]
    order = np.argsort(-scores)[:k]
    hits = [_hit(meta[int(i)], round(float(scores[int(i)]), 3))
            for i in order if int(i) < len(meta)]  # never index past meta (torn-store safety)
    raw_top = hits[0]["score"] if hits else 0.0  # best score BEFORE the floor
    # Apply the absolute score floor on BOTH paths. This was previously gated to
    # real embeddings, so it was silently ignored on the offline/hashing path
    # (DOC-01). 0 = off.
    if cfg.recall_min_score > 0:
        hits = [h for h in hits if h["score"] >= cfg.recall_min_score]
    # Relevance signal so an off-topic query doesn't feed Claude confident-looking
    # junk. Real embeddings → cosine threshold. The hashing fallback's cosine isn't
    # calibrated, so there we use lexical overlap between the query and the best
    # hit (no shared content words ⇒ low confidence) — this is what makes
    # low_confidence work with no model at all (DOC-01).
    if not hits:
        low_conf = True
    elif embedder.mode == "ollama":
        low_conf = hits[0]["score"] < 0.5
    else:
        low_conf = _lexical_overlap(query, hits[0].get("text", "")) == 0
    # top_score reflects what is actually RETURNED (RECALL-03); raw_top_score keeps
    # the pre-floor best for transparency.
    doc = load_graph(cfg)
    return {"status": "ok", "project": cfg.project, "query": query,
            "synopsis": ((doc or {}).get("synopsis", "") or "")[:_MAX_SYNOPSIS],
            # The mode this memory was last BUILT in (accurate|classical|fast) — so a
            # recall over a basic-mode memory is transparent, not silently assumed rich.
            "memory_mode": (doc or {}).get("stats", {}).get("mode"),
            "top_score": (hits[0]["score"] if hits else 0.0),
            "raw_top_score": raw_top, "low_confidence": low_conf, "hits": hits}


def _lexical(query: str, meta: list[dict], k: int, cfg: Config) -> dict:
    """Fallback when the query embedding's dimension != the stored matrix (e.g. the
    embedding backend changed since digest — an offline hash store queried with
    Ollama up). It keeps the SAME relevance contract as the main path so an
    off-topic query stays declinable (DOC-01): `low_confidence`, `top_score`,
    `raw_top_score`, and a (capped) `synopsis` are all present."""
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
            "synopsis": ((doc or {}).get("synopsis", "") or "")[:_MAX_SYNOPSIS],
            "memory_mode": (doc or {}).get("stats", {}).get("mode"),
            "top_score": top, "raw_top_score": top,
            "low_confidence": not hits, "hits": hits}


def overview(cfg: Config) -> dict:
    with locks.read_lock(cfg):
        doc = load_graph(cfg)
    if not doc:
        return {"status": "no_memory", "project": cfg.project}
    return {"status": "ok", "project": cfg.project,
            "synopsis": (doc.get("synopsis", "") or "")[:_MAX_SYNOPSIS],
            "stats": doc.get("stats", {}),
            "themes": [{"label": c["label"],
                        "summary": (c.get("summary", "") or "")[:_MAX_HIT_TEXT]}
                       for c in doc.get("communities", [])][:20]}
