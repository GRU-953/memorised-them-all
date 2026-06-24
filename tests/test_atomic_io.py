"""WP-100 (R-19 / contract [C2]): ONE shared crash-safe atomic writer, and the converted
`.md` write now goes through it (the last non-atomic write in the engine).

Before this, `convert.py` did a plain `out.write_text(...)` (R-19) — a crash mid-write
could leave a torn `.md` that the next digest would ingest — while `store.py` and
`setup.py` each carried their *own* `_atomic_write_text`, which had drifted (the setup copy
grew a Windows `os.replace` retry the store copy lacked). These pin: a single writer with
the crash-safe + byte-identical-newline contract, used everywhere.

Offline, dependency-light (only the shared writer + source text).
"""
from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("MTA_AUTO_UPDATE", "off")

import pytest

from mta.core import _io


def test_atomic_write_roundtrip_and_lf(tmp_path):
    p = tmp_path / "sub" / "note.md"          # parent dir is created
    _io.atomic_write_text(p, "x\ny\n")
    assert p.read_text(encoding="utf-8") == "x\ny\n"
    assert p.read_bytes() == b"x\ny\n"        # newline="" → no CRLF translation, byte-identical cross-OS
    _io.atomic_write_text(p, "z")             # overwrite is atomic too
    assert p.read_text(encoding="utf-8") == "z"


def test_failed_commit_leaves_previous_file_intact(tmp_path, monkeypatch):
    p = tmp_path / "keep.md"
    _io.atomic_write_text(p, "ORIGINAL")
    # Simulate a crash at the commit point (a non-PermissionError → raised immediately).
    def boom(src, dst):
        raise OSError("simulated disk-full at os.replace")
    monkeypatch.setattr(_io.os, "replace", boom)
    with pytest.raises(OSError):
        _io.atomic_write_text(p, "NEW-BUT-DOOMED")
    # The previous valid file survives untouched (never a torn write), and the staging
    # temp is cleaned up rather than left behind.
    assert p.read_text(encoding="utf-8") == "ORIGINAL"
    assert not list(tmp_path.glob("*.mta-tmp"))


def test_single_shared_writer_no_duplication():
    # store/render and setup/clients all route through the ONE _io writer — no copy-paste
    # divergence ([C2]).
    from mta.core import setup, store
    assert store._atomic_write_text is _io.atomic_write_text
    assert setup._atomic_write_text is _io.atomic_write_text


def test_convert_md_write_is_atomic():
    # The converted-.md write uses the crash-safe writer, and the old torn-write call is gone.
    src = (Path(__file__).resolve().parents[1] / "mta" / "core" / "convert.py").read_text(encoding="utf-8")
    assert "atomic_write_text(out" in src
    assert "out.write_text(" not in src
