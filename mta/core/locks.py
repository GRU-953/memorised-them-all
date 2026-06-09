"""Cross-process project locking — single-writer / multi-reader.

A mutating operation (digest, reset, forget) takes an EXCLUSIVE lock on the
project; readers (recall, overview) take a SHARED lock. This guarantees:

* two digests on one project never interleave (no torn ``graph.json`` ↔
  ``vectors.npz`` pair, no lost converted files);
* a reader never observes a half-updated graph/vectors pair;
* ``forget`` / ``reset`` never race a concurrent digest.

A separate *named* lock primitive (``named_lock``) is still available for any
operation that needs cross-process serialisation outside the per-project read/write
locks.

Lock files live under ``MTA_HOME/state/locks/`` — **not** inside the project dir,
so ``forget``/``reset`` (which ``rmtree`` the project dir) can't delete a held
lock. ``flock`` is advisory and auto-released when the fd closes or the holding
process dies, so stale locks are impossible. On Windows (no ``flock``) we use
``msvcrt`` exclusive locking for both modes (correct; just less reader
concurrency). If no locking primitive is available the lock degrades to a no-op
so the engine never hangs.
"""
from __future__ import annotations

import contextlib
import os
import time
from pathlib import Path

from .config import Config

try:
    import fcntl
    _BACKEND = "fcntl"
except ImportError:  # pragma: no cover - Windows
    try:
        import msvcrt
        _BACKEND = "msvcrt"
    except ImportError:  # pragma: no cover
        _BACKEND = None


def _key_path(cfg: Config, key: str) -> Path:
    d = cfg.state_dir / "locks"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{key}.lock"


def _try_lock(fd: int, exclusive: bool) -> bool:
    if _BACKEND == "fcntl":
        flag = (fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH) | fcntl.LOCK_NB
        try:
            fcntl.flock(fd, flag)
            return True
        except OSError:
            return False
    if _BACKEND == "msvcrt":  # pragma: no cover - Windows (exclusive-only)
        try:
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            return True
        except OSError:
            return False
    return False  # no backend → best-effort no-op


def _unlock(fd: int) -> None:
    try:
        if _BACKEND == "fcntl":
            fcntl.flock(fd, fcntl.LOCK_UN)
        elif _BACKEND == "msvcrt":  # pragma: no cover - Windows
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
    except OSError:
        pass


@contextlib.contextmanager
def named_lock(cfg: Config, key: str, *, exclusive: bool = True,
               timeout: float = 900.0):
    """Acquire a cross-process lock; yields True if held, False if best-effort.

    Polls up to ``timeout`` seconds, then proceeds WITHOUT the lock rather than
    hanging the engine forever (degraded mode). ``flock`` auto-releases on fd
    close / process death, so this can never deadlock on a stale lock.
    """
    path = _key_path(cfg, key)
    fd = os.open(str(path), os.O_RDWR | os.O_CREAT, 0o644)
    acquired = False
    try:
        deadline = time.monotonic() + max(0.0, timeout)
        while True:
            if _try_lock(fd, exclusive):
                acquired = True
                break
            if _BACKEND is None or time.monotonic() >= deadline:
                break
            time.sleep(0.1)
        if not acquired and _BACKEND is not None:
            # Timed out (not "no backend"): we proceed WITHOUT the lock rather than
            # hang — but say so, since the single-writer guarantee isn't held here.
            import sys
            print(f"[mta] warning: timed out acquiring "
                  f"{'exclusive' if exclusive else 'shared'} lock '{key}' after "
                  f"{timeout:.0f}s — proceeding without it.", file=sys.stderr)
        yield acquired
    finally:
        if acquired:
            _unlock(fd)
        try:
            os.close(fd)
        except OSError:
            pass


def write_lock(cfg: Config, timeout: float = 900.0):
    """Exclusive project lock for mutating ops (digest / reset / forget)."""
    return named_lock(cfg, f"project-{cfg.project}", exclusive=True, timeout=timeout)


def read_lock(cfg: Config, timeout: float = 120.0):
    """Shared project lock for readers (recall / overview)."""
    return named_lock(cfg, f"project-{cfg.project}", exclusive=False, timeout=timeout)
