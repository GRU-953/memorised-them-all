"""Deterministic, model-free text embeddings.

A token "hashing trick" maps each text to a fixed 256-dimension L2-normalised
vector — no model, no network, no GPU. The same text always yields the same vector,
which is what makes the whole pipeline (segmentation → resolution → recall) byte-stable
across runs and machines. It has no semantic similarity (this is a deliberate v2
tradeoff — recall degrades to lexical-overlap grade), but it never blocks a digest and
needs no download.

Nothing here returns text to the caller; embeddings are numeric vectors only.
"""
from __future__ import annotations

import hashlib
import re

import numpy as np

from .config import Config

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
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self._dim = _FALLBACK_DIM

    @property
    def mode(self) -> str:
        return "hash"

    def embed(self, texts: list[str], kind: str = "document") -> np.ndarray:
        """Embed a list of texts → (n, 256) L2-normalised float32 matrix.

        Always the deterministic hashing embedding. ``kind`` ("document"/"query")
        is accepted as a no-op for call-site compatibility.
        """
        if not texts:
            return np.zeros((0, _FALLBACK_DIM), dtype=np.float32)
        mat = np.vstack([_hash_embed_one(t) for t in texts]).astype(np.float32)
        return _normalize(mat)


def cosine(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Cosine similarity matrix between two already-normalised stacks."""
    if a.size == 0 or b.size == 0:
        return np.zeros((a.shape[0], b.shape[0]), dtype=np.float32)
    return a @ b.T
