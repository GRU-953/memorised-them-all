"""WP-65 — setup hardening: ${HOME} path resolution, OCR-language resilience,
all-file-types text fallback, and Claude auto-config. Fully offline.
"""
from __future__ import annotations

import json
import os

os.environ.setdefault("MTA_NO_OLLAMA", "1")
os.environ.setdefault("MTA_AUTO_UPDATE", "off")

from mta.core import convert
from mta.core import setup as setupmod
from mta.core.config import Config, _resolve_home


# ---- ${HOME} / MTA_HOME resolution (the digest-blocking bug) ----------------

def test_resolve_home_expands_dollar_home(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))  # Windows: Path.home()/expanduser use USERPROFILE
    monkeypatch.setenv("MTA_HOME", "${HOME}/.memorised-them-all")
    assert _resolve_home() == tmp_path / ".memorised-them-all"


def test_resolve_home_expands_tilde(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))  # Windows: Path.home()/expanduser use USERPROFILE
    monkeypatch.setenv("MTA_HOME", "~/mem")
    assert _resolve_home() == tmp_path / "mem"


def test_resolve_home_falls_back_on_unexpandable(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))  # Windows: Path.home()/expanduser use USERPROFILE
    monkeypatch.delenv("MTA_NONEXIST_VAR", raising=False)
    monkeypatch.setenv("MTA_HOME", "${MTA_NONEXIST_VAR}/x")
    assert _resolve_home() == tmp_path / ".memorised-them-all"


def test_resolve_home_falls_back_on_relative(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))  # Windows: Path.home()/expanduser use USERPROFILE
    monkeypatch.setenv("MTA_HOME", "relative/not/absolute")
    assert _resolve_home() == tmp_path / ".memorised-them-all"


def test_config_home_resolves_and_writes(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))  # Windows: Path.home()/expanduser use USERPROFILE
    monkeypatch.setenv("MTA_HOME", "${HOME}/.memorised-them-all")
    cfg = Config()
    assert cfg.home == tmp_path / ".memorised-them-all"
    cfg.ensure_dirs()  # the original failure: couldn't create dirs under a literal ${HOME}
    assert cfg.state_dir.exists()


# ---- OCR language: eng+ben default + graceful degradation -------------------

def test_ocr_default_is_eng_ben(monkeypatch):
    monkeypatch.delenv("MTA_OCR_LANG", raising=False)
    assert Config().ocr_lang == "eng+ben"


def test_resolve_ocr_lang_drops_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(convert, "_installed_ocr_langs", lambda: frozenset({"eng"}))
    cfg = Config(home=tmp_path); cfg.ocr_lang = "eng+ben"
    assert convert._resolve_ocr_lang(cfg) == "eng"


def test_resolve_ocr_lang_keeps_both_when_present(monkeypatch, tmp_path):
    monkeypatch.setattr(convert, "_installed_ocr_langs", lambda: frozenset({"eng", "ben"}))
    cfg = Config(home=tmp_path); cfg.ocr_lang = "eng+ben"
    assert convert._resolve_ocr_lang(cfg) == "eng+ben"


def test_resolve_ocr_lang_best_effort_when_unenumerable(monkeypatch, tmp_path):
    monkeypatch.setattr(convert, "_installed_ocr_langs", lambda: frozenset())
    cfg = Config(home=tmp_path); cfg.ocr_lang = "eng+ben"
    assert convert._resolve_ocr_lang(cfg) == "eng+ben"  # trust the request


# ---- all file types: plain-text fallback for unknown extensions -------------

def test_unknown_text_extension_digested(tmp_path):
    f = tmp_path / "notes.xyz"
    f.write_text("Project Aurora kickoff with the Nordic Grid Authority.", encoding="utf-8")
    text, method = convert._try_unknown_text(f)
    assert method == "text-fallback" and text and "Aurora" in text


def test_unknown_text_preserves_unicode(tmp_path):
    f = tmp_path / "doc.xyz"
    f.write_text("আকিজ গ্রুপ এবং Nordic Grid Authority", encoding="utf-8")  # Bangla + Latin
    text, method = convert._try_unknown_text(f)
    assert method == "text-fallback" and "Nordic Grid Authority" in text


def test_binary_unknown_not_digested(tmp_path):
    f = tmp_path / "blob.xyz"
    f.write_bytes(b"\x00\x01\x02\x03 binary \x00 data \xff\xfe")
    text, method = convert._try_unknown_text(f)
    assert text is None and method == "binary"


def test_convert_file_unknown_text_is_ok(tmp_path):
    src = tmp_path / "script.pyx"
    src.write_text("# Aurora config\nkey = value\nNordic Grid Authority lead.\n", encoding="utf-8")
    res = convert.convert_file(src, tmp_path / "out", Config(home=tmp_path))
    assert res.status == "ok" and res.method == "text-fallback"


def test_convert_file_unknown_binary_unsupported(tmp_path):
    src = tmp_path / "blob.bin"
    src.write_bytes(b"\x00\xff" * 200)
    res = convert.convert_file(src, tmp_path / "out", Config(home=tmp_path))
    assert res.status == "unsupported"


# ---- Claude auto-config (the "Claude Setup file") ---------------------------

def test_setup_claude_merges_and_is_idempotent(monkeypatch, tmp_path):
    desktop = tmp_path / "claude_desktop_config.json"
    desktop.write_text(json.dumps({"preferences": {"x": 1}, "coworkUserFilesPath": "/u"}), encoding="utf-8")
    monkeypatch.setattr(setupmod, "claude_desktop_config_path", lambda: desktop)
    monkeypatch.setattr(setupmod, "claude_code_config_path", lambda: tmp_path / "absent.json")
    monkeypatch.setattr(setupmod, "_mta_command", lambda: ["/opt/homebrew/bin/mta", "serve"])

    res = setupmod.setup_claude()
    d = json.loads(desktop.read_text())
    assert d["preferences"] == {"x": 1} and d["coworkUserFilesPath"] == "/u"   # preserved
    assert d["mcpServers"]["memorised-them-all"] == {
        "command": "/opt/homebrew/bin/mta", "args": ["serve"]}
    assert res["targets"]["claude_desktop"]["changed"] is True
    assert res["targets"]["claude_desktop"].get("backup")                       # backup made

    res2 = setupmod.setup_claude()  # idempotent
    assert res2["targets"]["claude_desktop"]["changed"] is False


def test_setup_claude_creates_when_absent_and_bakes_env(monkeypatch, tmp_path):
    desktop = tmp_path / "sub" / "claude_desktop_config.json"
    monkeypatch.setattr(setupmod, "claude_desktop_config_path", lambda: desktop)
    monkeypatch.setattr(setupmod, "claude_code_config_path", lambda: tmp_path / "absent.json")
    monkeypatch.setattr(setupmod, "_mta_command", lambda: ["mta", "serve"])
    setupmod.setup_claude(env={"MTA_OCR_LANG": "eng+ben"})
    entry = json.loads(desktop.read_text())["mcpServers"]["memorised-them-all"]
    assert entry["command"] == "mta" and entry["env"]["MTA_OCR_LANG"] == "eng+ben"
