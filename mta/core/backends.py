"""WP-23 — pluggable inference backends for text generation + embeddings.

The engine's two model-dependent steps — LLM extraction/summaries and text
embeddings — are funnelled through this one module so they can target either:

* **Ollama** (default) — the native ``/api/{generate,embeddings}`` API plus the
  on-demand lifecycle in :mod:`mta.core.lifecycle` (lazy start, idle stop). The
  behaviour is byte-for-byte what it was before this module existed.
* an **OpenAI-compatible** server — ``/v1/{chat/completions,embeddings}`` at
  ``MTA_BACKEND_URL`` (LM Studio, llama.cpp's server, vLLM, or any local endpoint
  speaking the OpenAI protocol). Opt-in via ``MTA_BACKEND``.

Selection is config-only; nothing else in the pipeline changes. Vision (image OCR)
and audio transcription stay on Ollama / local tools — this seam covers text
generation and embeddings.

**Invariants.** The default path is unchanged and 100% local. An OpenAI-compatible
backend is the user's explicit choice; it defaults to a *loopback* URL, and pointing
it at a non-local endpoint is the user's decision (warned once on stderr). When a
backend is unreachable these helpers return ``None`` so the callers fall back to
classical extraction / hashing embeddings — a digest still succeeds offline.
Nothing here returns text to the model: generation feeds summaries/extraction and
embeddings are numeric only (token-free).
"""
from __future__ import annotations

import json
import socket
import sys
import urllib.error
import urllib.request
from urllib.parse import urlparse

from .config import Config
from .lifecycle import OllamaManager

# Aliases that all mean "an OpenAI-compatible /v1 server".
_OPENAI_ALIASES = {
    "openai", "openai-compatible", "openai_compat", "compat",
    "lmstudio", "lm-studio", "llamacpp", "llama.cpp", "llama-cpp", "vllm",
}
_DEFAULT_URLS = {
    "lmstudio": "http://127.0.0.1:1234/v1",
    "lm-studio": "http://127.0.0.1:1234/v1",
    "llamacpp": "http://127.0.0.1:8080/v1",
    "llama.cpp": "http://127.0.0.1:8080/v1",
    "llama-cpp": "http://127.0.0.1:8080/v1",
    "vllm": "http://127.0.0.1:8000/v1",
}
_DEFAULT_OPENAI_URL = "http://127.0.0.1:1234/v1"
_warned: set[str] = set()


def backend_kind(cfg: Config) -> str:
    """``'ollama'`` (the default / ``auto``) or ``'openai'`` (any compatible server)."""
    name = (getattr(cfg, "backend", "") or "auto").strip().lower()
    return "openai" if name in _OPENAI_ALIASES else "ollama"


def _openai_base(cfg: Config) -> str:
    name = (getattr(cfg, "backend", "") or "").strip().lower()
    url = (getattr(cfg, "backend_url", "") or "").strip()
    return (url or _DEFAULT_URLS.get(name, _DEFAULT_OPENAI_URL)).rstrip("/")


def _is_local(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host in ("127.0.0.1", "localhost", "::1") or host.startswith("127.")


def _warn_once(key: str, msg: str) -> None:
    if key not in _warned:
        _warned.add(key)
        sys.stderr.write(f"[mta] {msg}\n")
        sys.stderr.flush()


def _warn_if_nonlocal(base: str) -> None:
    if not _is_local(base):
        _warn_once(f"nonlocal:{base}",
                   f"backend URL {base} is not loopback — content will leave this "
                   "machine. That is your explicit choice; the local-only guarantee "
                   "no longer holds for this backend.")


def _openai_headers(cfg: Config) -> dict:
    key = (getattr(cfg, "backend_key", "") or "").strip()
    return {"Authorization": f"Bearer {key}"} if key else {}


def _post(url: str, payload: dict, headers: dict, timeout: float) -> dict:
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


# ---- text generation --------------------------------------------------------

def generate(cfg: Config, ollama: OllamaManager, prompt: str, *,
             json_format: bool = False, num_predict: int = 320,
             temperature: float = 0.1, wait: float = 20, timeout: float = 180) -> str | None:
    """Generate text (stripped) or ``None`` on any failure (→ caller's fallback)."""
    if backend_kind(cfg) == "openai":
        return _openai_generate(cfg, prompt, json_format=json_format,
                                max_tokens=num_predict, temperature=temperature, timeout=timeout)

    # Ollama native (default) — identical to the pre-WP-23 inline calls.
    if not ollama.ensure_running(wait=wait):
        return None
    payload = {"model": cfg.extract_model, "prompt": prompt, "stream": False,
               "options": {"temperature": temperature, "num_predict": num_predict}}
    if json_format:
        payload["format"] = "json"
    try:
        data = _post(f"{ollama.host}/api/generate", payload, {}, timeout)
        ollama.touch()
        return (data.get("response") or "").strip() or None
    except Exception:  # noqa: BLE001
        return None


def _openai_generate(cfg: Config, prompt: str, *, json_format: bool,
                     max_tokens: int, temperature: float, timeout: float) -> str | None:
    base = _openai_base(cfg)
    _warn_if_nonlocal(base)
    payload = {"model": cfg.extract_model,
               "messages": [{"role": "user", "content": prompt}],
               "temperature": temperature, "max_tokens": max_tokens, "stream": False}
    if json_format:
        payload["response_format"] = {"type": "json_object"}
    try:
        data = _post(f"{base}/chat/completions", payload, _openai_headers(cfg), timeout)
        choices = data.get("choices") or []
        if not choices:
            return None
        return (choices[0].get("message", {}).get("content") or "").strip() or None
    except Exception:  # noqa: BLE001
        return None


# ---- embeddings -------------------------------------------------------------

def embed(cfg: Config, ollama: OllamaManager, texts: list[str], *,
          wait: float = 20, timeout: float = 60) -> list[list[float]] | None:
    """Return one embedding vector per text, or ``None`` on failure (→ hashing fallback)."""
    if not texts:
        return []
    if backend_kind(cfg) == "openai":
        return _openai_embed(cfg, texts, timeout=timeout)

    if not (cfg.embed_model and ollama.ensure_running(wait=wait)):
        return None
    ollama.touch()
    out: list[list[float]] = []
    for text in texts:
        try:
            data = _post(f"{ollama.host}/api/embeddings",
                         {"model": cfg.embed_model, "prompt": text}, {}, timeout)
        except Exception:  # noqa: BLE001
            return None
        emb = data.get("embedding")
        if not emb:
            return None
        out.append(emb)
    return out


def _openai_embed(cfg: Config, texts: list[str], *, timeout: float) -> list[list[float]] | None:
    base = _openai_base(cfg)
    _warn_if_nonlocal(base)
    try:
        data = _post(f"{base}/embeddings", {"model": cfg.embed_model, "input": texts},
                     _openai_headers(cfg), timeout)
        rows = data.get("data") or []
        if len(rows) != len(texts):
            return None
        rows = sorted(rows, key=lambda r: r.get("index", 0))  # be order-safe
        out = [r.get("embedding") for r in rows]
        return out if all(out) else None
    except Exception:  # noqa: BLE001
        return None


# ---- health probe -----------------------------------------------------------

def inference_ok(cfg: Config, ollama: OllamaManager, timeout: float = 15.0) -> bool | None:
    """Probe whether text generation ACTUALLY works right now — a tiny real call.

    ``OllamaManager.is_up()`` only checks ``/api/tags``, which stays green when the
    Ollama *launcher* is reachable but its inference runner (``llama-server``) is
    broken or the model isn't pulled. That is the exact "silent degradation" users
    hit: status looks healthy, yet every generate 500s, so a digest quietly falls
    back to classical/hash extraction with no signal. This does a 1-token generate
    so the result reflects real inference health, not just reachability.

    Returns ``True`` (generation works), ``False`` (reachable but generation
    definitively failed — broken runner / model not pulled — i.e. degraded), or
    ``None`` when the result is INCONCLUSIVE: a paid OpenAI-compatible backend (don't
    bill it just to probe), the launcher being unreachable (it may simply be
    idle-stopped and start fine on the real call), or a slow cold model-load that
    exceeds ``timeout`` (don't cry "degraded" for a model that's merely warming up).
    The False/None split matters: callers warn only on a *definitive* break, so a
    routine idle-stopped or cold-loading engine never triggers a false alarm.
    """
    if backend_kind(cfg) == "openai":
        return None  # never spend tokens/credits on a remote endpoint just to probe
    if not ollama.is_up():
        return None  # unreachable now ≠ broken: ensure_running() may start it fine
    try:
        # A 200 with a "response" key = the runner answered (content may be tiny).
        data = _post(f"{ollama.host}/api/generate",
                     {"model": cfg.extract_model, "prompt": "ping", "stream": False,
                      "options": {"num_predict": 1, "temperature": 0.0}},
                     {}, timeout)
        return isinstance(data, dict) and "response" in data
    except (socket.timeout, TimeoutError):
        return None  # slow / cold model load — inconclusive, NOT a definitive break
    except urllib.error.URLError as e:
        # A read/connect timeout wrapped by urllib is still inconclusive; any other
        # URLError (connection refused) or HTTPError (500 broken runner / 404 model
        # not pulled) is a definitive failure → degraded.
        if isinstance(getattr(e, "reason", None), (socket.timeout, TimeoutError)):
            return None
        return False
    except Exception:  # noqa: BLE001 — any other failure means inference isn't usable
        return False


# ---- reporting --------------------------------------------------------------

def describe(cfg: Config) -> dict:
    """Compact backend descriptor for ``memory_status`` (no secrets)."""
    if backend_kind(cfg) == "openai":
        base = _openai_base(cfg)
        return {"kind": "openai-compatible", "url": base, "local": _is_local(base),
                "gen_model": cfg.extract_model, "embed_model": cfg.embed_model}
    return {"kind": "ollama", "url": cfg.ollama_host, "local": _is_local(cfg.ollama_host),
            "gen_model": cfg.extract_model, "embed_model": cfg.embed_model}
