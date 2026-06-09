"""WP-80 — v2 corpus handling: skip categories, no-extension sniffing, archive
expansion, content-hash dedup. Fully offline and deterministic."""
from __future__ import annotations

import os
import zipfile

os.environ.setdefault("MTA_AUTO_UPDATE", "off")

from mta.core.config import Config
from mta.core.convert import convert_file


def _cfg(tmp_path, **over):
    c = Config(home=tmp_path / "home")
    for k, v in over.items():
        setattr(c, k, v)
    return c


# ---- skip categories (never read; status='skipped') ---------------------------------
def test_skip_categories(tmp_path):
    cases = {
        "photo.jpg": "media", "clip.mp4": "media", "talk.mp3": "media",
        "Sutonny.ttf": "font", "brand.otf": "font",
        "policy.pdf.gdrive": "gdrive-pointer", "sheet.gsheet": "gdrive-pointer",
        "scratch.tmp": "junk", ".DS_Store": "junk", "Thumbs.db": "junk",
    }
    for name, cat in cases.items():
        f = tmp_path / name
        f.write_bytes(b"x" * 32)            # content is irrelevant — name-based skip
        res = convert_file(f, tmp_path / "out", _cfg(tmp_path))
        assert res.status == "skipped" and res.method == "skipped-type", (name, res.status)
        assert res.error == cat, (name, res.error, cat)


def test_skip_switches_can_be_disabled(tmp_path):
    f = tmp_path / "photo.png"
    f.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)   # real-ish PNG header, no OCR dep
    res = convert_file(f, tmp_path / "out", _cfg(tmp_path, skip_media=False, ocr_mode="off"))
    # With media skipping off and OCR off, an image converts to nothing → empty/unsupported,
    # but it must NOT be 'skipped-type' (the switch was honoured).
    assert res.method != "skipped-type"


def test_text_files_still_convert(tmp_path):
    f = tmp_path / "note.txt"
    f.write_text("Aurora budget approved.", encoding="utf-8")
    res = convert_file(f, tmp_path / "out", _cfg(tmp_path))
    assert res.status == "ok"


# ---- no-extension Office/zip sniffing ------------------------------------------------
def test_no_extension_xlsx_is_sniffed(tmp_path):
    # Build a minimal real .xlsx via openpyxl if available, else fall back to checking
    # that a PK-magic file at least routes through the sniff path (not 'binary').
    target = tmp_path / "Rural data (Missining 1)"   # the real corpus case: no extension
    try:
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws["A1"] = "Helios cohort"
        ws["B1"] = 42
        wb.save(target)
    except ImportError:
        # minimal zip with PK magic — MarkItDown will fail it, but it must not be
        # classified as plain binary without trying.
        with zipfile.ZipFile(target, "w") as z:
            z.writestr("content.txt", "hello")
    res = convert_file(target, tmp_path / "out", _cfg(tmp_path))
    # Either MarkItDown read it (ok + sniffed) or it failed cleanly — never 'binary'.
    assert res.error != "binary"
    if res.status == "ok":
        assert "sniffed-zip" in res.method
