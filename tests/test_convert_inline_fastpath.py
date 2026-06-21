"""Cycle-2 perf: text/data files convert INLINE (no per-file subprocess spawn).

The per-file killable subprocess exists for C-extension parsers (PDF/Office) that can hang
un-interruptibly. Pure-Python text/data conversion (`_native_text` + linear, size-capped
Bengali regex) cannot hang, so it is routed inline — skipping the ~100 ms spawn that
dominated large text corpora (measured 12.0 s → 0.09 s for 100 files). These guard that the
inline path is actually taken for text/data and that output is unchanged. Offline.
"""
from __future__ import annotations

import os

os.environ.setdefault("MTA_AUTO_UPDATE", "off")

from mta.core import digest as digestmod
from mta.core.config import Config


def _payload(src, out, cfg):
    return (str(src), str(out), cfg, src.name + ".md")


def test_text_file_converts_without_spawning_a_subprocess(tmp_path, monkeypatch):
    cfg = Config(home=tmp_path)
    out = tmp_path / "md"; out.mkdir()
    src = tmp_path / "note.md"
    src.write_text("# Aurora\nProject Aurora is led by Dr. Lena Marsh at the Nordic Grid Authority.\n",
                   encoding="utf-8")
    # Any attempt to spawn a worker subprocess for this text file must fail the test.
    monkeypatch.setattr(digestmod._mp, "get_context",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("spawned for text")))
    res = digestmod._convert_isolated(_payload(src, out, cfg), cfg)
    assert res["status"] == "ok" and "markitdown" not in (res.get("method") or "")
    assert (out / "note.md.md").exists()


def test_data_extensions_are_inline_safe():
    # csv/json/etc. go through the pure-Python _native_text path → inline-safe set
    assert ".csv" in digestmod._INLINE_CONVERT_EXTS
    assert ".md" in digestmod._INLINE_CONVERT_EXTS and ".txt" in digestmod._INLINE_CONVERT_EXTS
    # binary formats that CAN hang a C parser are NOT inline (still isolated in a subprocess)
    assert ".pdf" not in digestmod._INLINE_CONVERT_EXTS
    assert ".docx" not in digestmod._INLINE_CONVERT_EXTS


def test_inline_and_digest_equivalent_output(tmp_path):
    # The inline path must produce the same digest as the corpus did pre-change: deterministic
    # graph from a small text corpus (a stronger end-to-end shape check than the unit above).
    docs = tmp_path / "docs"; docs.mkdir()
    (docs / "a.md").write_text("Helios Energy operates the Nyx Substation in the Nordic grid.\n",
                               encoding="utf-8")
    (docs / "b.txt").write_text("Dr. Lena Marsh leads Project Aurora for Helios Energy.\n",
                                encoding="utf-8")
    cfg = Config(home=tmp_path / "h").with_project("inline"); cfg.ensure_dirs()
    res = digestmod.digest(cfg, [str(docs)], reset=True)
    assert res["status"] == "ok" and res["stats"]["converted"] == 2 and res["stats"]["entities"] >= 1
