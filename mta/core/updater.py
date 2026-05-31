"""Auto-update — always run the latest Microsoft MarkItDown (and our own deps).

A background, throttled (once/day) check upgrades the MarkItDown engine straight
from upstream ``microsoft/markitdown`` and refreshes the rest of the dependency
set, then reports whether a newer release of *this* tool exists. Upgrades are
installed into the active virtualenv and take effect on the next launch. Opt out
with ``MTA_AUTO_UPDATE=off``. Never blocks a digest and never touches the network
synchronously on the request path.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import urllib.request

from .config import Config

MARKITDOWN_SPEC = ("markitdown[all] @ git+https://github.com/microsoft/"
                   "markitdown.git#subdirectory=packages/markitdown")
SELF_REPO = "GRU-953/memorised-them-all"
_THROTTLE_SECONDS = 24 * 3600


def _stamp(cfg: Config) -> Path:
    return cfg.state_dir / "last_update_check"


def _due(cfg: Config) -> bool:
    p = _stamp(cfg)
    try:
        return (time.time() - p.stat().st_mtime) >= _THROTTLE_SECONDS
    except OSError:
        return True


def _touch(cfg: Config) -> None:
    cfg.state_dir.mkdir(parents=True, exist_ok=True)
    _stamp(cfg).write_text(str(time.time()))


def _pip(*args: str) -> bool:
    try:
        r = subprocess.run([sys.executable, "-m", "pip", *args],
                           capture_output=True, text=True, timeout=900)
        return r.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def update_markitdown() -> bool:
    """Upgrade MarkItDown to the latest upstream commit."""
    return _pip("install", "-U", MARKITDOWN_SPEC)


def latest_self_release() -> str | None:
    try:
        url = f"https://api.github.com/repos/{SELF_REPO}/releases/latest"
        req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read()).get("tag_name")
    except Exception:  # noqa: BLE001
        return None


def run_check(cfg: Config, force: bool = False) -> dict:
    """Synchronous update pass (used by `mta update` and the daemon)."""
    if not force and not cfg.auto_update:
        return {"status": "disabled"}
    if not force and not _due(cfg):
        return {"status": "throttled"}
    result = {"status": "ok", "markitdown_updated": update_markitdown(),
              "latest_release": latest_self_release(), "current": _current_version()}
    _touch(cfg)
    return result


def _current_version() -> str:
    from .. import __version__
    return __version__


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
