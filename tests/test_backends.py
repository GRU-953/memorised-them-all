"""WP-23 — pluggable inference backends (Ollama default + OpenAI-compatible).

Offline: the Ollama path is exercised in its disabled state (→ callers fall back),
and the OpenAI-compatible path is tested with the HTTP boundary (`backends._post`)
mocked, so no network and no model are needed.
"""
from __future__ import annotations

import os

os.environ.setdefault("MTA_NO_OLLAMA", "1")
os.environ.setdefault("MTA_AUTO_UPDATE", "off")

import pytest

from mta.core import backends
from mta.core.config import Config
from mta.core.lifecycle import OllamaManager


def _cfg(tmp_path, **kw):
    cfg = Config(home=tmp_path)
    for key, value in kw.items():
        setattr(cfg, key, value)
    return cfg


# ---- backend selection ------------------------------------------------------

def test_backend_kind_defaults_to_ollama(tmp_path):
    assert backends.backend_kind(_cfg(tmp_path)) == "ollama"
    assert backends.backend_kind(_cfg(tmp_path, backend="auto")) == "ollama"
    assert backends.backend_kind(_cfg(tmp_path, backend="ollama")) == "ollama"


def test_backend_kind_openai_aliases(tmp_path):
    for name in ("openai", "lmstudio", "lm-studio", "llamacpp", "vllm", "openai-compatible"):
        assert backends.backend_kind(_cfg(tmp_path, backend=name)) == "openai", name


def test_openai_base_defaults_and_override(tmp_path):
    assert backends._openai_base(_cfg(tmp_path, backend="lmstudio")) == "http://127.0.0.1:1234/v1"
    assert backends._openai_base(_cfg(tmp_path, backend="llamacpp")) == "http://127.0.0.1:8080/v1"
    assert backends._openai_base(
        _cfg(tmp_path, backend="openai", backend_url="http://127.0.0.1:9/v1/")) == "http://127.0.0.1:9/v1"


# ---- Ollama path falls through when disabled (→ caller's deterministic fallback)

def test_generate_none_when_ollama_disabled(tmp_path, monkeypatch):
    monkeypatch.setenv("MTA_NO_OLLAMA", "1")
    cfg = _cfg(tmp_path)
    assert backends.generate(cfg, OllamaManager(cfg), "hello") is None


def test_embed_none_when_ollama_disabled(tmp_path, monkeypatch):
    monkeypatch.setenv("MTA_NO_OLLAMA", "1")
    cfg = _cfg(tmp_path)
    assert backends.embed(cfg, OllamaManager(cfg), ["a", "b"]) is None
    assert backends.embed(cfg, OllamaManager(cfg), []) == []


# ---- OpenAI-compatible path (HTTP mocked) -----------------------------------

def test_openai_generate_parses_and_builds_request(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, backend="lmstudio")
    seen = {}

    def fake_post(url, payload, headers, timeout):
        seen.update(url=url, payload=payload)
        return {"choices": [{"message": {"content": "  hi there  "}}]}

    monkeypatch.setattr(backends, "_post", fake_post)
    out = backends.generate(cfg, OllamaManager(cfg), "prompt", json_format=True, num_predict=50)
    assert out == "hi there"
    assert seen["url"].endswith("/chat/completions")
    assert seen["payload"]["response_format"] == {"type": "json_object"}
    assert seen["payload"]["max_tokens"] == 50


def test_openai_embed_parses_and_orders(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, backend="openai", backend_url="http://127.0.0.1:1234/v1")

    def fake_post(url, payload, headers, timeout):
        assert url.endswith("/embeddings")
        return {"data": [{"index": 1, "embedding": [0.3, 0.4]},
                         {"index": 0, "embedding": [0.1, 0.2]}]}  # out of order

    monkeypatch.setattr(backends, "_post", fake_post)
    assert backends.embed(cfg, OllamaManager(cfg), ["a", "b"]) == [[0.1, 0.2], [0.3, 0.4]]


def test_openai_embed_length_mismatch_is_none(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, backend="openai")
    monkeypatch.setattr(backends, "_post",
                        lambda *a, **k: {"data": [{"index": 0, "embedding": [1.0]}]})
    assert backends.embed(cfg, OllamaManager(cfg), ["a", "b"]) is None


def test_openai_auth_header_when_key_set(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, backend="openai", backend_key="sk-local-xyz")
    seen = {}
    monkeypatch.setattr(backends, "_post",
                        lambda url, payload, headers, timeout:
                        seen.update(headers=headers) or {"choices": [{"message": {"content": "ok"}}]})
    backends.generate(cfg, OllamaManager(cfg), "p")
    assert seen["headers"]["Authorization"] == "Bearer sk-local-xyz"


def test_openai_errors_return_none(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, backend="openai")

    def boom(*a, **k):
        raise OSError("connection refused")

    monkeypatch.setattr(backends, "_post", boom)
    assert backends.generate(cfg, OllamaManager(cfg), "p") is None
    assert backends.embed(cfg, OllamaManager(cfg), ["x"]) is None


def test_nonlocal_backend_warns_once(tmp_path, monkeypatch, capsys):
    backends._warned.clear()
    cfg = _cfg(tmp_path, backend="openai", backend_url="http://example.com/v1")
    monkeypatch.setattr(backends, "_post",
                        lambda *a, **k: {"choices": [{"message": {"content": "x"}}]})
    backends.generate(cfg, OllamaManager(cfg), "p")
    backends.generate(cfg, OllamaManager(cfg), "p")
    assert capsys.readouterr().err.count("not loopback") == 1


# ---- describe ---------------------------------------------------------------

def test_describe(tmp_path):
    d = backends.describe(_cfg(tmp_path))
    assert d["kind"] == "ollama" and d["local"] is True
    d2 = backends.describe(_cfg(tmp_path, backend="openai", backend_url="http://127.0.0.1:1234/v1"))
    assert d2["kind"] == "openai-compatible" and d2["local"] is True


# ---- Embedder integration ---------------------------------------------------

def test_embedder_uses_backend_and_reports_mode(tmp_path, monkeypatch):
    from mta.core import embed as embed_mod
    cfg = _cfg(tmp_path, backend="openai")
    monkeypatch.setattr(
        backends, "_post",
        lambda url, payload, headers, timeout:
        {"data": [{"index": i, "embedding": [float(i), 1.0, 2.0]}
                  for i in range(len(payload["input"]))]})
    emb = embed_mod.Embedder(cfg, OllamaManager(cfg))
    mat = emb.embed(["x", "y"])
    assert mat.shape == (2, 3)
    assert emb.mode == "openai"


def test_embedder_falls_back_to_hash_when_unavailable(tmp_path, monkeypatch):
    monkeypatch.setenv("MTA_NO_OLLAMA", "1")
    from mta.core import embed as embed_mod
    cfg = _cfg(tmp_path)  # default ollama backend, disabled
    emb = embed_mod.Embedder(cfg, OllamaManager(cfg))
    mat = emb.embed(["hello world"])
    assert emb.mode == "hash"
    assert mat.shape[1] == 256  # deterministic hashing dimension
