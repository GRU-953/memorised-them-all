"""Token-free recall — return only a tiny, relevant slice of memory.

The query is embedded with the same local model used at digest time, scored by
cosine against the stored recall units (theme summaries + entity cards), and the
top-k units are returned with provenance. Whole documents are never returned —
Claude gets a compact, citable slice, which is what keeps recall near-zero-token.
"""
from __future__ import annotations

import numpy as np

from .config import Config
from .embed import Embedder, cosine
from .lifecycle import OllamaManager
from .store import load_graph, load_vectors

# Hard per-hit caps so a verbose (or prompt-injected) local-model summary can
# never blow up Claude's context — the token-free guarantee must hold on the
# accurate path, not just the classical one.
_MAX_HIT_TEXT = 600
_MAX_HIT_DOCS = 5


def _hit(u: dict, score) -> dict:
    docs = u.get("docs", []) or []
    out = {"score": score, "kind": u.get("kind"), "label": u.get("label"),
           "text": (u.get("text") or "")[:_MAX_HIT_TEXT], "docs": docs[:_MAX_HIT_DOCS]}
    if len(docs) > _MAX_HIT_DOCS:
        out["doc_count"] = len(docs)
    return out


def recall(cfg: Config, query: str, k: int | None = None,
           ollama: OllamaManager | None = None) -> dict:
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
    hits = [_hit(meta[int(i)], round(float(scores[int(i)]), 3)) for i in order]
    raw_top = hits[0]["score"] if hits else 0.0  # best raw score (informative)
    # Relevance signal: with real embeddings, flag weak matches and (if a floor is
    # configured) drop hits below it — so an off-topic query doesn't feed Claude
    # confident-looking junk. The hashing fallback uses a different scale → no floor.
    low_conf = False
    if embedder.mode == "ollama":
        if cfg.recall_min_score > 0:
            hits = [h for h in hits if h["score"] >= cfg.recall_min_score]
        # Confidence reflects what's actually RETURNED: low if nothing survived
        # the floor, or the best surviving hit is weak.
        low_conf = (not hits) or hits[0]["score"] < 0.5
    top = hits[0]["score"] if hits else raw_top
    doc = load_graph(cfg)
    return {"status": "ok", "project": cfg.project, "query": query,
            "synopsis": (doc or {}).get("synopsis", ""),
            "top_score": top, "low_confidence": low_conf, "hits": hits}


def _lexical(query: str, meta: list[dict], k: int, cfg: Config) -> dict:
    q = set(query.lower().split())
    scored = []
    for u in meta:
        words = set((u.get("text") or "").lower().split())
        overlap = len(q & words)
        if overlap:
            scored.append((overlap, u))
    scored.sort(key=lambda x: -x[0])
    hits = [_hit(u, s) for s, u in scored[:k]]
    return {"status": "ok", "project": cfg.project, "query": query,
            "mode": "lexical", "hits": hits}


def overview(cfg: Config) -> dict:
    doc = load_graph(cfg)
    if not doc:
        return {"status": "no_memory", "project": cfg.project}
    return {"status": "ok", "project": cfg.project,
            "synopsis": doc.get("synopsis", ""), "stats": doc.get("stats", {}),
            "themes": [{"label": c["label"], "summary": c.get("summary", "")}
                       for c in doc.get("communities", [])][:20]}
