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


def recall(cfg: Config, query: str, k: int | None = None,
           ollama: OllamaManager | None = None) -> dict:
    # Hard-clamp k so a caller can never pull the whole graph's text into Claude's
    # context — the token-free guarantee depends on recall returning a tiny slice.
    k = max(1, min(int(k or cfg.recall_k), 50))
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
    hits = []
    for i in order:
        u = meta[int(i)]
        hits.append({"score": round(float(scores[int(i)]), 3),
                     "kind": u.get("kind"), "label": u.get("label"),
                     "text": u.get("text"), "docs": u.get("docs", [])})
    doc = load_graph(cfg)
    return {"status": "ok", "project": cfg.project, "query": query,
            "synopsis": (doc or {}).get("synopsis", ""), "hits": hits}


def _lexical(query: str, meta: list[dict], k: int, cfg: Config) -> dict:
    q = set(query.lower().split())
    scored = []
    for u in meta:
        words = set((u.get("text") or "").lower().split())
        overlap = len(q & words)
        if overlap:
            scored.append((overlap, u))
    scored.sort(key=lambda x: -x[0])
    hits = [{"score": s, "kind": u.get("kind"), "label": u.get("label"),
             "text": u.get("text"), "docs": u.get("docs", [])} for s, u in scored[:k]]
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
