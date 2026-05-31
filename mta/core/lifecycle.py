"""On-demand model-server lifecycle with a 5-minute idle shutdown.

The engine never keeps Ollama running when nothing is happening. The first call
that needs a local model starts ``ollama serve`` (only if it isn't already up),
and a background watchdog stops the instance *we* started once no work has
happened for ``MTA_IDLE`` seconds (default 300 = 5 minutes). A user's own / brew
Ollama is detected and left untouched.

Activity is tracked through a marker file so that process-pool workers in other
processes also count as "activity" — the watchdog reads the marker's mtime.
"""
from __future__ import annotations

import atexit
import os
import subprocess
import threading
import time
from pathlib import Path

import urllib.error
import urllib.request

from .config import Config


def _http_ok(url: str, timeout: float = 1.5) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status == 200
    except (urllib.error.URLError, OSError, ValueError):
        return False


class OllamaManager:
    """Starts Ollama on demand, stops it after idle — but only if we started it."""

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.host = cfg.ollama_host.rstrip("/")
        self._marker = cfg.state_dir / "last_use"
        self._started_by_us = False
        self._proc: subprocess.Popen | None = None
        self._watchdog: threading.Thread | None = None
        self._stop_evt = threading.Event()
        self._lock = threading.Lock()

    @staticmethod
    def _disabled() -> bool:
        # Hard offline switch (used by tests/CI and air-gapped runs).
        return os.environ.get("MTA_NO_OLLAMA", "").lower() in ("1", "true", "yes", "on")

    # ---- availability -------------------------------------------------
    def is_up(self) -> bool:
        if self._disabled():
            return False
        return _http_ok(f"{self.host}/api/tags")

    def touch(self) -> None:
        """Record activity (cross-process, via marker mtime)."""
        try:
            self.cfg.state_dir.mkdir(parents=True, exist_ok=True)
            self._marker.write_text(str(time.time()))
        except OSError:
            pass

    def _idle_for(self) -> float:
        try:
            return time.time() - self._marker.stat().st_mtime
        except OSError:
            return 0.0

    # ---- start / stop -------------------------------------------------
    def ensure_running(self, wait: float = 30.0) -> bool:
        """Guarantee a reachable Ollama; start one if needed. Returns availability."""
        if self._disabled():
            return False
        self.touch()
        if self.is_up():
            return True
        with self._lock:
            if self.is_up():
                return True
            if not _which("ollama"):
                return False
            try:
                self._proc = subprocess.Popen(
                    ["ollama", "serve"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except OSError:
                return False
            self._started_by_us = True
            atexit.register(self.stop)
            deadline = time.time() + wait
            while time.time() < deadline:
                if self.is_up():
                    self._start_watchdog()
                    return True
                time.sleep(0.5)
        return self.is_up()

    def stop(self) -> None:
        """Stop only the instance we launched."""
        self._stop_evt.set()
        with self._lock:
            if self._started_by_us and self._proc and self._proc.poll() is None:
                self._proc.terminate()
                try:
                    self._proc.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    self._proc.kill()
            self._started_by_us = False
            self._proc = None

    # ---- watchdog -----------------------------------------------------
    def _start_watchdog(self) -> None:
        if self._watchdog and self._watchdog.is_alive():
            return
        self._stop_evt.clear()

        def _loop():
            idle = max(30, self.cfg.idle_seconds)
            while not self._stop_evt.wait(min(15, idle / 4)):
                if self._idle_for() >= idle:
                    self.stop()
                    return

        self._watchdog = threading.Thread(target=_loop, daemon=True,
                                          name="mta-idle-watchdog")
        self._watchdog.start()


def _which(prog: str) -> str | None:
    import shutil
    return shutil.which(prog)
