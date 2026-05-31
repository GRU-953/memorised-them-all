"""Local text embeddings via Ollama (``nomic-embed-text`` by default).

When Ollama or the embedding model is unavailable we fall back to a deterministic
hashing embedding (a token "hashing trick" into a fixed dimension). The fallback
keeps the whole pipeline — segmentation, resolution, recall — working offline and
in CI without any model download. It is obviously weaker than a real embedding,
but it is stable and never blocks a digest.

Nothing here returns text to the caller; embeddings are numeric vectors only.
"""
from __future__ import annotations

import hashlib
import json
import re
from functools import lru_cache

import urllib.error
import urllib.request

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

    def _ollama_embed(self, text: str) -> list[float] | None:
        url = f"{self.ollama.host}/api/embeddings"
        payload = json.dumps({"model": self.cfg.embed_model, "prompt": text}).encode()
        req = urllib.request.Request(url, data=payload,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                data = json.loads(r.read())
            emb = data.get("embedding")
            return emb if emb else None
        except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError):
            return None

    def _prefix(self, kind: str) -> str:
        # nomic-embed-text is trained with task prefixes; without them short
        # strings embed almost identically. Other models get no prefix.
        if "nomic" in (self.cfg.embed_model or "").lower():
            return "search_query: " if kind == "query" else "search_document: "
        return ""

    def embed(self, texts: list[str], kind: str = "document") -> np.ndarray:
        """Embed a list of texts → (n, dim) L2-normalised float32 matrix.

        ``kind`` is "document" (default) or "query"; it only changes the task
        prefix for prefix-aware models (nomic).
        """
        if not texts:
            return np.zeros((0, _FALLBACK_DIM), dtype=np.float32)

        use_ollama = self.cfg.embed_model and self.ollama.ensure_running(wait=20)
        if use_ollama:
            self.ollama.touch()
            prefix = self._prefix(kind)
            vecs: list[list[float]] = []
            ok = True
            for t in texts:
                emb = self._ollama_embed((prefix + t)[:8000])
                if emb is None:
                    ok = False
                    break
                vecs.append(emb)
            if ok and vecs:
                self._mode = "ollama"
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
