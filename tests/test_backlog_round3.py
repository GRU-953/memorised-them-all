"""WP-73 — stress-test loop Round 3 (lower-severity backlog).

Each test pins one Round-3 fix so it can't regress. Fully offline (no Ollama, no network).
"""
from __future__ import annotations

import os

os.environ.setdefault("MTA_NO_OLLAMA", "1")
os.environ.setdefault("MTA_AUTO_UPDATE", "off")

from mta.core.config import Config


# ---- (1) 0-byte file → "empty", not "unsupported"/"failed" --------------------------
def test_zero_byte_file_is_empty(tmp_path):
    from mta.core.convert import convert_file
    for name in ("placeholder.txt", "mystery.xyz"):          # known + unknown extension
        f = tmp_path / name
        f.write_bytes(b"")
        res = convert_file(f, tmp_path / "out", Config(home=tmp_path / "h"))
        assert res.status == "empty", (name, res.status)


# ---- (2) BOM / UTF-16 decode (Windows "Unicode" files) ------------------------------
def test_utf16_bom_text_decodes_not_mojibake(tmp_path):
    from mta.core.convert import convert_file
    f = tmp_path / "win.txt"
    f.write_bytes(b"\xff\xfe" + "Aurora budget approved.".encode("utf-16-le"))  # UTF-16-LE BOM
    res = convert_file(f, tmp_path / "out", Config(home=tmp_path / "h"))
    assert res.status == "ok"
    body = (tmp_path / "out").glob("*.md").__next__().read_text(encoding="utf-8")
    assert "Aurora budget approved." in body            # decoded correctly, no NUL mojibake
    assert "\x00" not in body


def test_utf16_unknown_ext_not_misflagged_binary(tmp_path):
    from mta.core.convert import convert_file
    f = tmp_path / "notes.xyz"                                # unknown extension
    f.write_bytes(b"\xff\xfe" + "hello world".encode("utf-16-le"))
    res = convert_file(f, tmp_path / "out", Config(home=tmp_path / "h"))
    # Its interleaved NULs previously tripped the binary heuristic → "unsupported".
    assert res.status == "ok" and "bom" in (res.method or "")


# ---- (4) cgroup-aware memory_gb -----------------------------------------------------
def test_memory_gb_capped_by_cgroup(monkeypatch):
    from mta.core import platform as plat
    monkeypatch.delenv("MTA_MEMORY_GB", raising=False)
    monkeypatch.setattr(plat, "_host_memory_gb", lambda: 64.0)
    monkeypatch.setattr(plat, "_cgroup_mem_limit_gb", lambda: 2.0)
    plat.memory_gb.cache_clear()                          # memory_gb is lru_cached
    assert plat.memory_gb() == 2.0                        # container cap wins over big host
    monkeypatch.setattr(plat, "_cgroup_mem_limit_gb", lambda: None)
    plat.memory_gb.cache_clear()
    assert plat.memory_gb() == 64.0                       # no cap → host total
    plat.memory_gb.cache_clear()                          # don't poison other tests


def test_memory_gb_override_still_wins(monkeypatch):
    from mta.core import platform as plat
    monkeypatch.setenv("MTA_MEMORY_GB", "3")
    plat.memory_gb.cache_clear()
    assert plat.memory_gb() == 3.0
    plat.memory_gb.cache_clear()


# ---- (6) out-of-tree symlink policy -------------------------------------------------
def test_expand_skips_out_of_tree_symlink(tmp_path):
    from mta.core.digest import _expand
    tree = tmp_path / "tree"
    tree.mkdir()
    (tree / "inside.txt").write_text("Aurora budget approved.", encoding="utf-8")
    outside = tmp_path / "secret.txt"
    outside.write_text("TOP SECRET — not under the digested folder", encoding="utf-8")
    try:
        (tree / "leak.txt").symlink_to(outside)
    except (OSError, NotImplementedError):
        return  # filesystem without symlinks (some Windows) — nothing to assert
    names = {p.name for p in _expand([str(tree)])}
    assert "inside.txt" in names
    assert "leak.txt" not in names                        # escaping symlink skipped on a walk
    # …but an explicitly-named symlink is still honored (the user chose it).
    explicit = _expand([str(tree / "leak.txt")])
    assert any(p.name == "leak.txt" for p in explicit)
