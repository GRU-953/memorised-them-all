"""WP-11 — auto-configuration (R2): named profiles, persisted config, detection.

Profiles are toggled per-test via monkeypatch (so we don't set MTA_NO_OLLAMA at
import time the way the other suites do).
"""
from __future__ import annotations

import json
import os


def test_offline_profile_resolves_offline(tmp_path, monkeypatch):
    monkeypatch.setenv("MTA_HOME", str(tmp_path))
    monkeypatch.setenv("MTA_PROFILE", "offline")
    for k in ("MTA_NO_OLLAMA", "MTA_EXTRACT", "MTA_AUTO_UPDATE"):
        monkeypatch.delenv(k, raising=False)
    from mta.core.config import load
    cfg = load()
    assert cfg.profile_name == "offline"
    assert cfg.no_ollama is True
    assert cfg.extract_mode == "classical"
    assert cfg.auto_update is False
    # the profile's seeding must NOT leak into the process env
    assert os.environ.get("MTA_NO_OLLAMA") in (None, "")


def test_explicit_env_overrides_profile(tmp_path, monkeypatch):
    monkeypatch.setenv("MTA_HOME", str(tmp_path))
    monkeypatch.setenv("MTA_PROFILE", "offline")
    monkeypatch.setenv("MTA_AUTO_UPDATE", "on")     # explicit beats the profile's "off"
    from mta.core.config import load
    assert load().auto_update is True


def test_server_profile_sets_extract_workers(tmp_path, monkeypatch):
    monkeypatch.setenv("MTA_HOME", str(tmp_path))
    monkeypatch.setenv("MTA_PROFILE", "server")
    monkeypatch.delenv("MTA_EXTRACT_WORKERS", raising=False)
    from mta.core.config import load
    cfg = load()
    assert cfg.extract_workers == 3
    assert os.environ.get("MTA_EXTRACT_WORKERS") in (None, "")   # no leak


def test_unknown_profile_is_harmless(tmp_path, monkeypatch):
    monkeypatch.setenv("MTA_HOME", str(tmp_path))
    monkeypatch.setenv("MTA_PROFILE", "nonsense")
    from mta.core.config import load
    assert load().profile_name == "nonsense"   # recorded, no defaults applied


def test_persist_config_writes_snapshot(tmp_path, monkeypatch):
    monkeypatch.setenv("MTA_HOME", str(tmp_path))
    monkeypatch.delenv("MTA_PROFILE", raising=False)
    from mta.core.config import load, persist_config
    p = persist_config(load())
    assert p.exists()
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["profile"] == "micro"   # new default: safe 4 GB / no-GPU baseline
    assert "extract_model" in data and "no_ollama" in data and "markitdown_upstream" in data


def test_default_profile_is_micro_4gb_safe(tmp_path, monkeypatch):
    # New default (no MTA_PROFILE) must be safe on a 4 GB / no-GPU box: classical
    # extraction (no heavy LLM → can't OOM/thrash), vision off, tiny whisper.
    monkeypatch.setenv("MTA_HOME", str(tmp_path))
    for k in ("MTA_PROFILE", "MTA_EXTRACT", "MTA_VISION", "MTA_WHISPER_MODEL",
              "MTA_EMBED_MODEL", "MTA_WORKERS", "MTA_EXTRACT_WORKERS"):
        monkeypatch.delenv(k, raising=False)
    from mta.core.config import load
    c = load()
    assert c.profile_name == "micro"
    assert c.extract_mode == "classical"
    assert c.vision_mode == "off"
    assert c.whisper_model == "tiny"


def test_profile_auto_resolves_to_detected_tier(tmp_path, monkeypatch):
    monkeypatch.setenv("MTA_HOME", str(tmp_path))
    monkeypatch.setenv("MTA_PROFILE", "auto")
    from mta.core import platform
    from mta.core.config import load
    c = load()
    assert c.profile_name == platform.detect_tier()
    assert c.profile_name in ("micro", "small", "standard", "large")


def test_env_var_overrides_default_profile(tmp_path, monkeypatch):
    # A user opts up with a single knob; the explicit env var beats the micro profile.
    monkeypatch.setenv("MTA_HOME", str(tmp_path))
    monkeypatch.delenv("MTA_PROFILE", raising=False)
    monkeypatch.setenv("MTA_EXTRACT", "auto")
    from mta.core.config import load
    assert load().extract_mode == "auto"


def test_detect_tier_buckets(monkeypatch):
    from mta.core import platform
    for gb, want in [(4.0, "micro"), (8.0, "small"), (16.0, "standard"), (64.0, "large")]:
        platform.detect_tier.cache_clear()
        monkeypatch.setattr(platform, "memory_gb", lambda gb=gb: gb)
        assert platform.detect_tier() == want
    platform.detect_tier.cache_clear()


def test_worker_count_floor_one_under_6gb(monkeypatch):
    """Conversion pool clamps to ONE worker on a <6 GB box; 16/48 GB unchanged.

    Each markitdown/Office/PDF conversion worker can transiently hold a few hundred
    MB, so two concurrent workers can OOM a 4 GB box during the conversion stage —
    before any LLM is loaded. A <6 GB box therefore runs a single (sequential)
    worker. At 16/48 GB the prior ``cores ∧ (gb//2) ∧ 8`` sizing is unchanged:
    dropping the old ``max(2, …)`` floor is a no-op there (``gb//2`` is already ≥ 3),
    and the hard cap of 8 binds once cores ≥ 8.
    """
    from mta.core import platform
    # Pin perf-cores so the 16/48 GB assertions are deterministic across CI runners
    # (a 2-core GitHub runner would otherwise size those to 2, not the 8-cap).
    monkeypatch.setattr(platform, "performance_cores", lambda: 8)
    for gb, want in [(4.0, 1), (16.0, 8), (48.0, 8)]:
        monkeypatch.setattr(platform, "memory_gb", lambda gb=gb: gb)
        assert platform.worker_count() == want, f"{gb} GB → expected {want}"
    # An explicit request still wins, even on a sub-6 GB box (precedes the floor).
    monkeypatch.setattr(platform, "memory_gb", lambda: 4.0)
    assert platform.worker_count(requested=4) == 4


def test_summary_reports_gpu_and_lm_studio(tmp_path, monkeypatch):
    monkeypatch.setenv("MTA_HOME", str(tmp_path))
    from mta.core.platform import summary
    s = summary()
    assert s["gpu"] in ("mlx", "cuda", "rocm", "none")
    assert isinstance(s["lm_studio"], bool)


