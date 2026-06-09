"""WP-80 — model-free config (v2). No profiles, no models, no Ollama: ``load()`` is
just ``Config()`` with deterministic defaults. RAM-based conversion-worker sizing is
retained (it's CPU/RAM sizing, not model selection)."""
from __future__ import annotations

import json


def test_load_returns_model_free_config(tmp_path, monkeypatch):
    monkeypatch.setenv("MTA_HOME", str(tmp_path))
    from mta.core.config import Config, load
    c = load()
    assert isinstance(c, Config)
    # deterministic skip + archive defaults are ON out of the box
    assert c.skip_media and c.skip_fonts and c.skip_gdrive_pointers and c.skip_junk
    assert c.archive_recursive and c.archive_max_depth >= 1 and c.archive_max_entries >= 1
    # no model/profile/ollama attributes survive on the dataclass
    for attr in ("extract_model", "embed_model", "vision_model", "whisper_model",
                 "extract_mode", "fast", "no_ollama", "ollama_host", "profile_name",
                 "backend", "vision_mode", "transcribe_mode", "idle_seconds"):
        assert not hasattr(c, attr), f"{attr} should be gone in v2"


def test_persist_config_writes_model_free_snapshot(tmp_path, monkeypatch):
    monkeypatch.setenv("MTA_HOME", str(tmp_path))
    from mta.core.config import load, persist_config
    p = persist_config(load())
    assert p.exists()
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["engine"] == "deterministic" and data["model_free"] is True
    assert "skip_media" in data and "archive_recursive" in data and "ocr_lang" in data
    for k in ("profile", "extract_model", "embed_model", "vision_model",
              "whisper_model", "no_ollama", "extract_mode", "idle_seconds"):
        assert k not in data, f"{k} must not leak into the snapshot"


def test_skip_and_archive_flags_overridable(tmp_path, monkeypatch):
    monkeypatch.setenv("MTA_HOME", str(tmp_path))
    monkeypatch.setenv("MTA_SKIP_MEDIA", "off")
    monkeypatch.setenv("MTA_ARCHIVE_RECURSIVE", "off")
    from mta.core.config import load
    c = load()
    assert c.skip_media is False and c.archive_recursive is False


def test_worker_count_floor_one_under_6gb(monkeypatch):
    """Conversion pool clamps to ONE worker on a <6 GB box; 16/48 GB unchanged. RAM-based
    sizing is retained in v2 (each MarkItDown/Office/PDF worker can transiently hold a few
    hundred MB, so two concurrent workers can OOM a 4 GB box during conversion)."""
    from mta.core import platform
    monkeypatch.setattr(platform, "performance_cores", lambda: 8)
    for gb, want in [(4.0, 1), (16.0, 8), (48.0, 8)]:
        monkeypatch.setattr(platform, "memory_gb", lambda gb=gb: gb)
        assert platform.worker_count() == want, f"{gb} GB → expected {want}"
    monkeypatch.setattr(platform, "memory_gb", lambda: 4.0)
    assert platform.worker_count(requested=4) == 4   # explicit request still wins


def test_summary_is_model_free(tmp_path, monkeypatch):
    monkeypatch.setenv("MTA_HOME", str(tmp_path))
    from mta.core.platform import summary
    s = summary()
    assert s["model_free"] is True and s["engine"] == "deterministic"
    assert "gpu" not in s and "detected_tier" not in s and "lm_studio" not in s
