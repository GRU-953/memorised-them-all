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
    assert data["profile"] == "default"
    assert "extract_model" in data and "no_ollama" in data and "markitdown_upstream" in data


def test_summary_reports_gpu_and_lm_studio(tmp_path, monkeypatch):
    monkeypatch.setenv("MTA_HOME", str(tmp_path))
    from mta.core.platform import summary
    s = summary()
    assert s["gpu"] in ("mlx", "cuda", "rocm", "none")
    assert isinstance(s["lm_studio"], bool)


def test_disabled_respects_cfg_no_ollama(tmp_path, monkeypatch):
    monkeypatch.setenv("MTA_HOME", str(tmp_path))
    monkeypatch.delenv("MTA_NO_OLLAMA", raising=False)
    monkeypatch.setenv("MTA_PROFILE", "offline")
    from mta.core.config import load
    from mta.core.lifecycle import OllamaManager
    m = OllamaManager(load())          # cfg.no_ollama True via the offline profile
    assert m._disabled() is True
    assert m.ensure_running(wait=0.1) is False
