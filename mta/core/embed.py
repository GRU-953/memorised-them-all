"""Deterministic, model-free text embeddings.

A token "hashing trick" maps each text to a fixed 256-dimension L2-normalised
vector — no model, no network, no GPU. The same text always yields the same vector,
which is what makes the whole pipeline (segmentation → resolution → recall) byte-stable
across runs and machines. It has no semantic similarity (this is a deliberate v2
tradeoff — recall degrades to lexical-overlap grade), but it never blocks a digest and
needs no download.

**numpy-optional (WP-181a).** numpy is used only to vectorise the matrix when present;
the *merge decision* the resolver needs (cosine ≥ threshold) is reproduced byte-for-byte
without it (see ``embed_dot``). When numpy is absent the embedder returns plain Python
lists, recall still works (it reads the meta sidecar, never the matrix), and the
``vectors.npz`` matrix is simply not produced — so a fully numpy-free core can still
complete a digest and recall. Nothing here returns text to the caller; embeddings are
numeric vectors only.
"""
from __future__ import annotations

import hashlib
import math
import re

try:
    import numpy as np
    _HAVE_NUMPY = True
except Exception:  # noqa: BLE001 — numpy is optional; the core degrades to pure Python
    np = None  # type: ignore[assignment]
    _HAVE_NUMPY = False

from .config import Config

_FALLBACK_DIM = 256
_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _hash_buckets(text: str) -> list[float]:
    """Dense 256-bucket sums for a text, pre-normalisation, as a Python list. EXACTLY the
    same arithmetic as the numpy path (md5 bucket, sign from bit 8, ±1 accumulate) so the
    normalised vectors — and the merge decisions taken from them — are identical with or
    without numpy."""
    vec = [0.0] * _FALLBACK_DIM
    for tok in _TOKEN_RE.findall(text.lower()):
        h = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16)
        idx = h % _FALLBACK_DIM
        vec[idx] += 1.0 if (h >> 8) & 1 else -1.0
    return vec


def _normalize_py(vec: list[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in vec))
    if n == 0.0:
        return vec
    return [x / n for x in vec]


def _normalize(mat):  # numpy path
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return mat / norms


def _hash_embed_one(text: str):  # numpy path
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

    def embed(self, texts: list[str], kind: str = "document"):
        """Embed a list of texts → an (n, 256) L2-normalised matrix.

        With numpy: a float32 ``np.ndarray`` (unchanged). Without numpy: a list of
        normalised Python lists. Either is accepted by ``embed_dot`` (resolver) and
        ``store.save_vectors`` (which writes the ``.npz`` matrix only when it's a real
        ``ndarray``). ``kind`` ("document"/"query") is a no-op kept for call compatibility.
        """
        if _HAVE_NUMPY:
            if not texts:
                return np.zeros((0, _FALLBACK_DIM), dtype=np.float32)
            mat = np.vstack([_hash_embed_one(t) for t in texts]).astype(np.float32)
            return _normalize(mat)
        return [_normalize_py(_hash_buckets(t)) for t in texts]


def embed_dot(mat, i: int, j: int) -> float:
    """Cosine of two already-L2-normalised rows (rows are unit vectors → dot == cosine).

    Reproduces the SAME merge decision with or without numpy: with numpy it is exactly
    ``float(mat[i] @ mat[j])`` (so existing graphs stay byte-identical); without, a
    pure-Python float64 dot. The two differ only by ~1e-7, far below the ~1e-3 spacing of
    achievable hash-embedding cosines near the 0.92 merge threshold, so the boolean
    decision — and therefore the resolved graph — is identical either way (WP-181a)."""
    if _HAVE_NUMPY and isinstance(mat, np.ndarray):
        return float(mat[i] @ mat[j])
    a, b = mat[i], mat[j]
    return float(sum(x * y for x, y in zip(a, b)))


def cosine(a, b):
    """Cosine similarity matrix between two already-normalised numpy stacks (numpy only)."""
    if a.size == 0 or b.size == 0:
        return np.zeros((a.shape[0], b.shape[0]), dtype=np.float32)
    return a @ b.T
