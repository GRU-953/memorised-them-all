"""Local text embeddings via Ollama (``qwen3-embedding:0.6b`` by default).

When Ollama or the embedding model is unavailable we fall back to a deterministic
hashing embedding (a token "hashing trick" into a fixed dimension). The fallback
keeps the whole pipeline — segmentation, resolution, recall — working offline and
in CI without any model download. It is obviously weaker than a real embedding,
but it is stable and never blocks a digest.

Nothing here returns text to the caller; embeddings are numeric vectors only.
"""
from __future__ import annotations

import hashlib
import re

import numpy as np

from .config import Config
from .lifecycle import OllamaManager

_FALLBACK_DIM = 256
_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _normalize(mat: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return mat / norms


def _hash_embed_one(text: str) -> np.ndarray:
    vec = np.zeros(_FALLBACK_DIM, dtype=np.float32)
    toks = _TOKEN_RE.findall(text.lower())
    if not toks:
        return vec
    for tok in toks:
        h = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16)
        idx = h % _FALLBACK_DIM
        sign = 1.0 if (h >> 8) & 1 else -1.0
        vec[idx] += sign
    return vec


class Embedder:
    def __init__(self, cfg: Config, ollama: OllamaManager | None = None):
        self.cfg = cfg
        self.ollama = ollama or OllamaManager(cfg)
        self._dim: int | None = None
        self._mode: str | None = None  # "ollama" | "hash"

    @property
    def mode(self) -> str:
        if self._mode is None:
            self.embed(["probe"])
        return self._mode or "hash"

    def _prefix(self, kind: str) -> str:
        # Some embedders want task prefixes; without them short strings embed almost
        # identically. nomic uses search_query/search_document on both sides; Qwen3-
        # Embedding wants a one-line instruction on the QUERY side only (documents get
        # none) — this measurably improves its retrieval. Anything else gets no prefix.
        name = (self.cfg.embed_model or "").lower()
        if "nomic" in name:
            return "search_query: " if kind == "query" else "search_document: "
        if "qwen3-embedding" in name:
            return ("Instruct: Retrieve passages relevant to the query.\nQuery: "
                    if kind == "query" else "")
        return ""

    def embed(self, texts: list[str], kind: str = "document") -> np.ndarray:
        """Embed a list of texts → (n, dim) L2-normalised float32 matrix.

        ``kind`` is "document" (default) or "query"; it only changes the task
        prefix for prefix-aware models (nomic).
        """
        if not texts:
            return np.zeros((0, _FALLBACK_DIM), dtype=np.float32)

        from . import backends
        prefix = self._prefix(kind)
        vecs = backends.embed(self.cfg, self.ollama,
                              [(prefix + t)[:8000] for t in texts])
        if vecs:
            # "ollama" | "openai" — used downstream to label real vs hashing embeddings.
            self._mode = backends.backend_kind(self.cfg)
            mat = np.asarray(vecs, dtype=np.float32)
            self._dim = mat.shape[1]
            return _normalize(mat)

        # Fallback: deterministic hashing embedding.
        self._mode = "hash"
        self._dim = _FALLBACK_DIM
        mat = np.vstack([_hash_embed_one(t) for t in texts]).astype(np.float32)
        return _normalize(mat)


def cosine(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Cosine similarity matrix between two already-normalised stacks."""
    if a.size == 0 or b.size == 0:
        return np.zeros((a.shape[0], b.shape[0]), dtype=np.float32)
    return a @ b.T
