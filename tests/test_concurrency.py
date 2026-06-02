"""WP-14 — cross-process locking (LIFE-01) + lifecycle concurrency (PIPE-03).

Offline (``MTA_NO_OLLAMA=1``) so they run on the standard CI matrix across all
three OSes — exercising the POSIX ``fcntl`` path and the Windows ``msvcrt`` path.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("MTA_NO_OLLAMA", "1")
os.environ.setdefault("MTA_AUTO_UPDATE", "off")
os.environ.setdefault("MTA_EXTRACT", "classical")

REPO = Path(__file__).resolve().parents[1]
SAMPLE = REPO / "sample"


def _cfg(tmp_path, project="t"):
    os.environ["MTA_HOME"] = str(tmp_path)
    from mta.core.config import load
    return load().with_project(project)


def test_write_lock_is_exclusive(tmp_path):
    from mta.core import locks
    cfg = _cfg(tmp_path, "lk")
    with locks.write_lock(cfg, timeout=0.3) as a:
        assert a is True
        # A second exclusive acquire (separate fd) must fail fast — already held.
        with locks.write_lock(cfg, timeout=0.3) as b:
            assert b is False


def test_read_locks_are_shared(tmp_path):
    if os.name == "nt":
        pytest.skip("msvcrt provides exclusive locks only (no shared mode)")
    from mta.core import locks
    cfg = _cfg(tmp_path, "lk2")
    with locks.read_lock(cfg, timeout=0.3) as a:
        with locks.read_lock(cfg, timeout=0.3) as b:
            assert a is True and b is True  # multiple readers OK (POSIX)


def test_write_excludes_read(tmp_path):
    from mta.core import locks
    cfg = _cfg(tmp_path, "lk3")
    with locks.write_lock(cfg, timeout=0.3) as w:
        assert w is True
        with locks.read_lock(cfg, timeout=0.3) as r:
            assert r is False  # a reader is blocked while a writer holds the lock


def test_lock_file_lives_outside_project_dir(tmp_path):
    """forget()/reset rmtree the project dir; a held lock must survive that."""
    from mta.core import locks
    cfg = _cfg(tmp_path, "lk4")
    with locks.write_lock(cfg) as a:
        assert a is True
    lp = cfg.state_dir / "locks" / "project-lk4.lock"
    assert lp.exists()
    assert cfg.state_dir in lp.parents and cfg.project_dir not in lp.parents


def test_concurrent_digests_no_corruption(tmp_path):
    """A5: several digests on ONE project don't corrupt the store (torn pair)."""
    from concurrent.futures import ThreadPoolExecutor

    from mta.core.digest import digest
    from mta.core.store import load_graph, load_vectors

    def run(_i):
        cfg = _cfg(tmp_path, "shared")  # same project; fresh Config per thread
        return digest(cfg, [str(SAMPLE)])

    with ThreadPoolExecutor(max_workers=4) as ex:
        results = list(ex.map(run, range(4)))
    assert all(r["status"] == "ok" for r in results), results

    cfg = _cfg(tmp_path, "shared")
    g = load_graph(cfg)
    v = load_vectors(cfg)
    assert g is not None and v is not None
    # The graph<->vectors pair is consistent: every entity unit's ref is a node.
    node_ids = {n["id"] for n in g["nodes"]}
    _matrix, meta = v
    ent_refs = [u["ref"] for u in meta if u.get("kind") == "entity"]
    assert ent_refs and all(ref in node_ids for ref in ent_refs)
    assert not list(cfg.project_dir.glob("*.tmp"))  # no leftover temp files


def test_forget_serialises_via_write_lock(tmp_path):
    """forget() takes the project write lock and deletes cleanly after a digest."""
    from mta.core.digest import digest
    from mta.core.store import delete_project
    cfg = _cfg(tmp_path, "del")
    digest(cfg, [str(SAMPLE)])
    assert cfg.project_dir.exists()
    r = delete_project(cfg)
    assert r["status"] == "ok" and not cfg.project_dir.exists()


def test_ollama_unreachable_fast_fail(tmp_path, monkeypatch):
    """PIPE-03: a failed start sets a cooldown so we don't re-wait every call."""
    import time as _t

    from mta.core.lifecycle import OllamaManager
    monkeypatch.delenv("MTA_NO_OLLAMA", raising=False)  # un-disable for this test
    cfg = _cfg(tmp_path, "oll")
    m = OllamaManager(cfg)
    monkeypatch.setattr(m, "is_up", lambda: False)            # never comes up
    monkeypatch.setattr(m, "stop", lambda: None)              # neuter atexit hook
    monkeypatch.setattr("mta.core.lifecycle._which", lambda prog: "/usr/bin/ollama")
    monkeypatch.setattr("mta.core.lifecycle.subprocess.Popen", lambda *a, **k: object())

    t0 = _t.monotonic()
    assert m.ensure_running(wait=0.5) is False     # pays the ~0.5s start wait once
    slow = _t.monotonic() - t0
    t1 = _t.monotonic()
    assert m.ensure_running(wait=0.5) is False     # cooldown → returns immediately
    fast = _t.monotonic() - t1
    assert m._giveup_until > _t.monotonic()
    assert fast < slow                              # the cooldown short-circuited
