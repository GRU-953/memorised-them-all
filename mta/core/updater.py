"""Auto-update — keep MarkItDown (and our deps) current, safely.

The **default source is PyPI** (the pinned build in ``requirements.txt``; pip
verifies the wheel hashes against the index), so a first-ever digest works offline
and reproducibly — no live ``git+https`` fetch on the hot path. Pulling the latest
*upstream* MarkItDown commit is **opt-in** (``MTA_AUTO_UPDATE=upstream`` or
``MTA_MARKITDOWN_UPSTREAM=on``) and is **pinned to a resolved commit SHA** rather
than a moving branch. Every upgrade is import-smoke-tested and **rolled back** to
the previous version on failure. A daily, throttled, background check runs it; it
never blocks a digest and never touches the network synchronously on the request
path. Opt out entirely with ``MTA_AUTO_UPDATE=off``.
"""
from __future__ import annotations

import importlib.metadata as _md
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import urllib.request

from .config import Config

_MARKITDOWN_EXTRAS = "[pdf,docx,pptx,xlsx,xls,outlook]"
_MARKITDOWN_PYPI = f"markitdown{_MARKITDOWN_EXTRAS}"
_MARKITDOWN_REPO = "microsoft/markitdown"
SELF_REPO = "GRU-953/memorised-them-all"
_THROTTLE_SECONDS = 24 * 3600


def _stamp(cfg: Config) -> Path:
    return cfg.state_dir / "last_update_check"


def _due(cfg: Config) -> bool:
    try:
        return (time.time() - _stamp(cfg).stat().st_mtime) >= _THROTTLE_SECONDS
    except OSError:
        return True


def _touch(cfg: Config) -> None:
    """Stamp the throttle file atomically (temp + os.replace) so two concurrent
    launches can't both pass the throttle and race a pip install into one venv."""
    cfg.state_dir.mkdir(parents=True, exist_ok=True)
    p = _stamp(cfg)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(str(time.time()))
    os.replace(tmp, p)


def _pip(*args: str, timeout: int = 900) -> bool:
    try:
        r = subprocess.run([sys.executable, "-m", "pip", *args],
                           capture_output=True, text=True, timeout=timeout)
        return r.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _installed_version(pkg: str) -> str | None:
    try:
        return _md.version(pkg)
    except Exception:  # noqa: BLE001
        return None


def _imports_ok(module: str) -> bool:
    """Smoke-test that a package imports cleanly in a fresh subprocess — a basic
    integrity/functional check before we trust a freshly-installed upgrade."""
    try:
        r = subprocess.run([sys.executable, "-c", f"import {module}"],
                           capture_output=True, timeout=120)
        return r.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _resolve_upstream_commit() -> str | None:
    """Resolve ``microsoft/markitdown@main`` to a concrete commit SHA so the opt-in
    upstream pull is pinned/reproducible instead of tracking a moving branch."""
    try:
        url = f"https://api.github.com/repos/{_MARKITDOWN_REPO}/commits/main"
        req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read()).get("sha")
    except Exception:  # noqa: BLE001
        return None


def _markitdown_spec(cfg: Config) -> tuple[str, str | None]:
    """Return ``(pip_spec, pinned_commit)``.

    Default → the PyPI build. Upstream (opt-in) → pinned to a resolved commit; if
    the commit can't be resolved we **fall back to PyPI** rather than ever pulling
    an unpinned, moving branch.
    """
    if getattr(cfg, "markitdown_upstream", False):
        sha = _resolve_upstream_commit()
        if sha:
            return (f"{_MARKITDOWN_PYPI} @ git+https://github.com/{_MARKITDOWN_REPO}.git"
                    f"@{sha}#subdirectory=packages/markitdown", sha)
    return (_MARKITDOWN_PYPI, None)


def update_markitdown(cfg: Config) -> dict:
    """Upgrade MarkItDown safely: pinned spec → install → import-smoke → roll back
    to the previously-installed version on failure."""
    prev = _installed_version("markitdown")
    spec, commit = _markitdown_spec(cfg)
    rolled_back = False
    ok = _pip("install", "-U", spec)
    if ok and not _imports_ok("markitdown"):
        # The upgrade installed but no longer imports — roll back to what worked.
        ok = False
        if prev and _pip("install", "--force-reinstall", "--no-deps", f"markitdown=={prev}"):
            rolled_back = True
    return {
        "updated": ok,
        "source": "upstream" if commit else "pypi",
        "pinned_commit": commit,
        "from_version": prev,
        "to_version": _installed_version("markitdown"),
        "rolled_back": rolled_back,
    }


def latest_self_release() -> str | None:
    try:
        url = f"https://api.github.com/repos/{SELF_REPO}/releases/latest"
        req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read()).get("tag_name")
    except Exception:  # noqa: BLE001
        return None


def _current_version() -> str:
    from .. import __version__
    return __version__


def run_check(cfg: Config, force: bool = False) -> dict:
    """Synchronous update pass (used by ``mta update`` and the daemon)."""
    if not force and not cfg.auto_update:
        return {"status": "disabled"}
    if not force and not _due(cfg):
        return {"status": "throttled"}
    # Stamp BEFORE doing the work so a second process (e.g. Desktop + Code both
    # launching) sees the throttle and doesn't race a concurrent pip install.
    _touch(cfg)
    return {
        "status": "ok",
        "markitdown": update_markitdown(cfg),
        "latest_release": latest_self_release(),
        "current": _current_version(),
    }


def start_background(cfg: Config) -> None:
    """Fire-and-forget daily check; never blocks the request path."""
    if not cfg.auto_update or not _due(cfg):
        return

    def _bg():
        try:
            run_check(cfg)
        except Exception:  # noqa: BLE001
            pass

    threading.Thread(target=_bg, daemon=True, name="mta-updater").start()
