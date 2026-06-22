"""Shared crash-safe file I/O — the single atomic-write primitive ([C2]).

Historically `store.py` and `setup.py` each carried their own `_atomic_write_text`,
which drifted (the setup copy grew a Windows retry the store copy lacked). WP-100
collapses them into one writer so `convert.py`, `store.py`, `render.py`, `clients.py`
and `setup.py` all share the *same* crash-safe contract:

  stage to a UNIQUE temp file in the target's own directory (``mkstemp`` — two concurrent
  runs can't clobber a shared temp; same-filesystem so ``os.replace`` is never a
  cross-device ``OSError``) → ``flush`` + ``fsync`` → ``os.replace`` (the single commit
  point). A reader never sees a half-written file, and an interrupt (crash/power loss)
  leaves the *previous* valid file intact rather than a truncated one.

``encoding="utf-8"`` is explicit (Windows defaults to cp1252); ``newline=""`` disables
platform newline translation so converted ``.md`` / ``graph.json`` / ``memory.md`` are
**byte-identical across OSes** — the determinism invariant holds cross-machine, not just
same-OS. On Windows ``os.replace`` raises ``PermissionError`` if another process holds
the destination open without share-delete (a running MCP client editing its config), so
the commit is retried a few times before giving up, since the lock is usually momentary.
"""
from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path


def atomic_write_text(path: Path, text: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".mta-tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        for attempt in range(4):
            try:
                os.replace(tmp, path)
                break
            except PermissionError:          # Windows: dest held open without share-delete
                if attempt == 3:
                    raise
                time.sleep(0.15)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
