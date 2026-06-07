"""WP-72 — honest degraded-mode reporting.

Pins the behaviour for the silent-degradation roadblock: Ollama's launcher can be
reachable (``/api/tags`` 200) while its inference runner is broken or the model
isn't pulled, so every generate 500s and a digest quietly falls back to classical /
hashing with no signal. These tests assert the tool now SAYS SO — in ``memory_status``
(inference health), in the ``digest`` result (``degraded`` flag), and in ``recall``
(``memory_mode``). Fully offline (no Ollama, no network).
"""
from __future__ import annotations

import os

os.environ.setdefault("MTA_NO_OLLAMA", "1")
os.environ.setdefault("MTA_AUTO_UPDATE", "off")

from mta.core import backends
from mta.core.config import Config
from mta.core.lifecycle import OllamaManager


# ---- inference probe ---------------------------------------------------------
def test_inference_ok_false_when_ollama_unavailable(tmp_path):
    # Disabled/unreachable Ollama → inference is NOT usable → False (never crashes).
    cfg = Config(home=tmp_path, no_ollama=True)
    assert backends.inference_ok(cfg, OllamaManager(cfg)) is False


def test_inference_ok_none_for_remote_backend(tmp_path):
    # A paid OpenAI-compatible backend must NOT be billed just to run a health probe.
    cfg = Config(home=tmp_path, backend="openai")
    assert backends.inference_ok(cfg, OllamaManager(cfg)) is None


# ---- digest degraded flag ----------------------------------------------------
def _seed(tmp_path):
    src = tmp_path / "docs"
    src.mkdir()
    (src / "n.txt").write_text(
        "The Helios consortium funded Project Borealis in Oslo.", encoding="utf-8")
    return src


def test_digest_flags_degraded_when_llm_expected_but_unavailable(tmp_path):
    from mta.core.digest import digest
    src = _seed(tmp_path)
    # extract_mode=auto (the default) WANTS the LLM but falls back to classical when
    # Ollama is down → the result must say degraded=True with a human reason.
    cfg = Config(home=tmp_path / "h", extract_mode="auto", no_ollama=True, convert_timeout=60)
    d = digest(cfg, [str(src)])
    assert d["status"] == "ok"
    assert d["degraded"] is True and isinstance(d.get("degraded_reason"), str)
    assert d["stats"]["mode"] == "classical"


def test_digest_not_degraded_when_basic_mode_is_the_choice(tmp_path):
    from mta.core.digest import digest
    src = _seed(tmp_path)
    # fast=True is a deliberate basic-mode request → completing in classical is NOT
    # a degradation, so the flag stays False (no false alarm for micro/offline users).
    cfg = Config(home=tmp_path / "h", fast=True, convert_timeout=60)
    d = digest(cfg, [str(src)])
    assert d["status"] == "ok" and d["degraded"] is False


# ---- recall transparency -----------------------------------------------------
def test_recall_reports_memory_mode(tmp_path):
    from mta.core.digest import digest
    from mta.core.recall import recall
    src = _seed(tmp_path)
    cfg = Config(home=tmp_path / "h", fast=True, convert_timeout=60)
    digest(cfg, [str(src)])
    r = recall(cfg, "Helios consortium")
    assert r["status"] == "ok"
    assert r.get("memory_mode") == "fast"   # surfaced how the memory was built


# ---- memory_status honesty ---------------------------------------------------
def test_memory_status_reports_inference_health(tmp_path, monkeypatch):
    monkeypatch.setenv("MTA_HOME", str(tmp_path))
    monkeypatch.setenv("MTA_NO_OLLAMA", "1")
    from mta import server
    st = server.memory_status()
    assert st["status"] == "ok"
    assert st["ollama_inference"] in ("disabled", "down")  # never silently "ok"
    assert st["degraded"] is False                          # not "running but broken"
    assert isinstance(st["health"], str) and st["health"]   # always a plain-English line
