"""Auto-update safety (WP-10/13): offline-first default, opt-in pinned upstream,
import-smoke + rollback, atomic throttle. No network — pip and the commit resolver
are monkeypatched."""
from __future__ import annotations

import os

os.environ.setdefault("MTA_NO_OLLAMA", "1")
os.environ.setdefault("MTA_AUTO_UPDATE", "off")  # keep the background updater quiet


def _cfg(tmp_path, **env):
    os.environ["MTA_HOME"] = str(tmp_path)
    for k, v in env.items():
        os.environ[k] = v
    from mta.core.config import load
    return load()


def test_default_update_source_is_pypi(tmp_path, monkeypatch):
    """With no opt-in, the MarkItDown spec is the PyPI build — never a git URL."""
    from mta.core import updater
    cfg = _cfg(tmp_path)
    assert cfg.markitdown_upstream is False
    monkeypatch.setattr(updater, "_resolve_upstream_commit", lambda: "deadbeef")
    spec, commit = updater._markitdown_spec(cfg)
    assert "git+" not in spec and spec.startswith("markitdown[")
    assert commit is None


def test_upstream_opt_in_pins_commit(tmp_path, monkeypatch):
    from mta.core import updater
    try:
        cfg = _cfg(tmp_path, MTA_MARKITDOWN_UPSTREAM="on")
        assert cfg.markitdown_upstream is True
        monkeypatch.setattr(updater, "_resolve_upstream_commit", lambda: "abc123")
        spec, commit = updater._markitdown_spec(cfg)
        assert "git+https://github.com/microsoft/markitdown.git@abc123" in spec
        assert commit == "abc123"
    finally:
        os.environ.pop("MTA_MARKITDOWN_UPSTREAM", None)


def test_auto_update_upstream_value_enables_upstream(tmp_path):
    try:
        cfg = _cfg(tmp_path, MTA_AUTO_UPDATE="upstream")
        assert cfg.markitdown_upstream is True
        assert cfg.auto_update is True  # 'upstream' implies the check runs
    finally:
        os.environ["MTA_AUTO_UPDATE"] = "off"


def test_upstream_unresolvable_falls_back_to_pypi(tmp_path, monkeypatch):
    """If the upstream commit can't be resolved, never pull a moving branch."""
    from mta.core import updater
    try:
        cfg = _cfg(tmp_path, MTA_MARKITDOWN_UPSTREAM="on")
        monkeypatch.setattr(updater, "_resolve_upstream_commit", lambda: None)
        spec, commit = updater._markitdown_spec(cfg)
        assert "git+" not in spec
        assert commit is None
    finally:
        os.environ.pop("MTA_MARKITDOWN_UPSTREAM", None)


def test_failed_import_triggers_rollback(tmp_path, monkeypatch):
    """A broken upgrade is rolled back to the previously-installed version, and
    `rolled_back` is reported only after the restored version is re-verified (WP-34)."""
    from mta.core import updater
    cfg = _cfg(tmp_path)
    calls = []
    monkeypatch.setattr(updater, "_installed_version", lambda pkg: "0.1.6")
    monkeypatch.setattr(updater, "_pip", lambda *a, **k: calls.append(a) or True)
    seq = iter([False, True])  # post-upgrade import fails → roll back → restored import OK
    monkeypatch.setattr(updater, "_imports_ok", lambda m: next(seq))
    res = updater.update_markitdown(cfg)
    assert res["updated"] is False
    assert res["rolled_back"] is True
    assert any("markitdown==0.1.6" in " ".join(c) for c in calls), calls


def test_successful_update_not_rolled_back(tmp_path, monkeypatch):
    from mta.core import updater
    cfg = _cfg(tmp_path)
    monkeypatch.setattr(updater, "_installed_version", lambda pkg: "0.1.7")
    monkeypatch.setattr(updater, "_pip", lambda *a, **k: True)
    monkeypatch.setattr(updater, "_imports_ok", lambda m: True)
    res = updater.update_markitdown(cfg)
    assert res["updated"] is True and res["rolled_back"] is False and res["source"] == "pypi"


def test_run_check_disabled(tmp_path):
    from mta.core import updater
    cfg = _cfg(tmp_path, MTA_AUTO_UPDATE="off")
    assert updater.run_check(cfg)["status"] == "disabled"


def test_throttle_stamp_is_atomic(tmp_path):
    from mta.core import updater
    cfg = _cfg(tmp_path, MTA_AUTO_UPDATE="on")
    try:
        updater._touch(cfg)
        assert updater._stamp(cfg).exists()
        assert not list(cfg.state_dir.glob("*.tmp"))  # no leftover temp
    finally:
        os.environ["MTA_AUTO_UPDATE"] = "off"
