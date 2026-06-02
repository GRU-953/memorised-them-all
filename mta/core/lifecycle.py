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

    # After a failed start (Ollama installed but unreachable), fast-fail for this
    # many seconds instead of re-paying the full `wait` on every call (PIPE-03).
    _GIVEUP_COOLDOWN = 60.0

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.host = cfg.ollama_host.rstrip("/")
        self._marker = cfg.state_dir / "last_use"
        self._started_by_us = False
        self._proc: subprocess.Popen | None = None
        self._watchdog: threading.Thread | None = None
        self._stop_evt = threading.Event()
        self._lock = threading.Lock()
        self._giveup_until = 0.0

    def _disabled(self) -> bool:
        # Hard offline switch — the resolved Config flag (set directly or by the
        # 'offline' profile), or the env var (air-gapped runs / tests / CI).
        if getattr(self.cfg, "no_ollama", False):
            return True
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
        # PIPE-03: if a recent start attempt failed (Ollama installed but
        # unreachable), don't re-pay the full `wait` on every call — fast-fail
        # until the cooldown elapses.
        if time.monotonic() < self._giveup_until:
            return False
        with self._lock:
            if self.is_up():
                return True
            from . import locks
            from .platform import bootstrap_path
            bootstrap_path()
            if not _which("ollama"):
                self._giveup_until = time.monotonic() + self._GIVEUP_COOLDOWN
                return False
            # Cross-process start lock: two processes (e.g. Desktop + Code) must
            # not both spawn `ollama serve` (A5 / DEP-08). Re-check is_up inside.
            with locks.named_lock(self.cfg, "ollama-start", exclusive=True,
                                  timeout=max(2.0, wait)):
                if self.is_up():
                    return True
                try:
                    self._proc = subprocess.Popen(
                        ["ollama", "serve"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except OSError:
                    self._giveup_until = time.monotonic() + self._GIVEUP_COOLDOWN
                    return False
                self._started_by_us = True
                atexit.register(self.stop)
                deadline = time.time() + wait
                while time.time() < deadline:
                    if self.is_up():
                        self._start_watchdog()
                        return True
                    time.sleep(0.5)
            # Spawned but never became reachable within `wait` → cool down.
            self._giveup_until = time.monotonic() + self._GIVEUP_COOLDOWN
        return self.is_up()

    def stop(self) -> None:
        """Stop only the instance we launched, including its child runner.

        `ollama serve` spawns a child runner process; terminating only the parent
        (the default on Windows, and sometimes on POSIX) would orphan it and hold
        the port. We tear down the whole process tree via psutil when available.
        """
        self._stop_evt.set()
        with self._lock:
            proc = self._proc
            if self._started_by_us and proc and proc.poll() is None:
                if not self._terminate_tree(proc.pid):
                    proc.terminate()
                # Reap the Popen child in both paths so it doesn't linger as a
                # zombie (psutil's wait_procs doesn't reap our Popen handle).
                try:
                    proc.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    proc.kill()
            self._started_by_us = False
            self._proc = None

    @staticmethod
    def _terminate_tree(pid: int) -> bool:
        """Terminate a process and all its children. Returns True if handled."""
        try:
            import psutil
        except Exception:
            return False
        try:
            parent = psutil.Process(pid)
            procs = parent.children(recursive=True) + [parent]
            for p in procs:
                try:
                    p.terminate()
                except psutil.Error:
                    pass
            _, alive = psutil.wait_procs(procs, timeout=8)
            for p in alive:
                try:
                    p.kill()
                except psutil.Error:
                    pass
            return True
        except psutil.Error:
            return False

    # ---- watchdog -----------------------------------------------------
    def _start_watchdog(self) -> None:
        if self._watchdog and self._watchdog.is_alive():
            return
        self._stop_evt.clear()

        def _loop():
            idle = max(5, self.cfg.idle_seconds)
            while not self._stop_evt.wait(max(1.0, min(15, idle / 4))):
                if self._idle_for() >= idle:
                    self.stop()
                    return

        self._watchdog = threading.Thread(target=_loop, daemon=True,
                                          name="mta-idle-watchdog")
        self._watchdog.start()


def _which(prog: str) -> str | None:
    import shutil
    return shutil.which(prog)
