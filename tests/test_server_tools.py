"""Cycle-3 coverage + correctness: exercise the 8 MCP tool handlers in `mta.server`.

These are the functions Claude/Gemini/etc. actually call. Covers happy paths AND the
argument-validation / error branches (`_err`), and asserts the token-free contract (every
result is a compact dict, never document contents). Offline.
"""
from __future__ import annotations

import os

os.environ.setdefault("MTA_AUTO_UPDATE", "off")

import pytest

from mta import server


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("MTA_HOME", str(tmp_path))
    monkeypatch.setenv("MTA_AUTO_UPDATE", "off")
    return tmp_path


# ---- argument-validation / error branches (the uncovered _err paths) --------

def test_error_branches(home):
    assert server.digest([])["status"] == "error"            # empty paths
    assert server.digest("not-a-list")["status"] == "error"
    assert server.convert([])["status"] == "error"
    assert server.recall("")["status"] == "error"            # empty query
    assert server.recall("   ")["status"] == "error"
    assert server.export_memory("")["status"] == "error"
    assert server.list_digestible("")["status"] == "error"


def test_list_digestible_not_found_and_ok(home, tmp_path):
    assert server.list_digestible(str(tmp_path / "nope"))["status"] == "not_found"
    d = tmp_path / "docs"; d.mkdir()
    (d / "a.md").write_text("hello", encoding="utf-8")
    (d / "img.png").write_bytes(b"\x89PNG\r\n")              # media skipped
    out = server.list_digestible(str(d))
    assert out["status"] == "ok" and out["count"] >= 1
    assert all("bytes" in f and "path" in f for f in out["files"])   # paths/sizes only — token-free


# ---- happy path across the lifecycle ----------------------------------------

def test_full_tool_lifecycle_is_token_free(home, tmp_path):
    docs = tmp_path / "docs"; docs.mkdir()
    (docs / "n.md").write_text("Project Aurora is led by Dr. Lena Marsh at Helios Energy.\n",
                               encoding="utf-8")
    dig = server.digest([str(docs)], project="srv")
    assert dig["status"] == "ok" and "conversion" in dig
    # convert
    cv = server.convert([str(docs / "n.md")], out_dir=str(tmp_path / "md"), project="srv")
    assert cv  # structured
    # recall returns a tiny cited slice, never the document body
    rc = server.recall("Aurora", project="srv")
    assert rc["status"] in ("ok", "no_memory")
    import json as _json
    assert len(_json.dumps(rc).encode()) < 100_000          # token-free byte bound
    # overview + status
    assert server.memory_overview(project="srv")["status"] in ("ok", "no_memory")
    st = server.memory_status()
    assert st["status"] == "ok" and st["backend"]["model_free"] is True
    # export + forget
    server.export_memory(str(tmp_path / "exp"), project="srv")
    assert server.forget(project="srv")["status"] in ("ok", "not_found")


def test_digest_exception_is_wrapped(home, monkeypatch):
    # a converter blowing up must come back as a structured error, never propagate
    monkeypatch.setattr(server, "run_digest",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    out = server.digest(["tests/fixtures"], project="x")
    assert out["status"] == "error" and "boom" in out["error"]


def test_build_server_registers_eleven_tools():
    srv = server.build_server()
    mgr = getattr(srv, "_tool_manager", None)
    names = {t.name for t in mgr.list_tools()}
    assert {"digest", "convert", "recall", "memory_overview", "export_memory",
            "list_digestible", "forget", "memory_status",
            "diff_memory", "import_memory", "merge_memory"} == names
