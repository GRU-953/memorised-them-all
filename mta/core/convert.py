"""Local, token-free conversion of any attachment to Markdown.

Conversion order of preference for each file:
  1. Native passthrough for text/markdown/csv/json/xml (no dependency needed).
  2. Microsoft **MarkItDown** (latest) for PDF/Office/HTML/EPub/…
  3. **Tesseract** OCR (optional, offline) for images and scanned/image-only PDFs.
  4. Recursive expansion of archives (zip/tar/gz/bz2/xz, + optional rar/7z).

v2 is **deterministic and model-free** — no Ollama, no embedding/vision/whisper models,
no GPU, no network. The function returns only metadata (paths, sizes, status) — never
file content — so a whole folder costs ~0 tokens. Missing optional dependencies degrade
to a clear ``unsupported``/``empty``/``skipped`` status rather than crashing a batch.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from .config import Config

# File-type groupings.
_TEXT_EXTS = {".txt", ".md", ".markdown", ".text", ".log", ".rst"}
_DATA_EXTS = {".csv", ".tsv", ".json", ".xml", ".yaml", ".yml", ".ndjson"}
_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tiff", ".tif", ".webp"}
_AUDIO_EXTS = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".aac"}
_MARKITDOWN_EXTS = {".pdf", ".docx", ".pptx", ".xlsx", ".xls", ".html", ".htm",
                    ".epub", ".msg", ".rtf", ".doc", ".ppt"}
# Archives (zip/tar/gz/… + rar/7z) are expanded recursively at the digest level
# (mta/core/archive.py) rather than converted as single documents.
from .archive import ARCHIVE_EXTS as _ARCHIVE_EXTS  # noqa: E402 (after stdlib imports)
from .archive import kind as _archive_kind  # noqa: E402
SUPPORTED_EXTS = (_TEXT_EXTS | _DATA_EXTS | _IMAGE_EXTS | _AUDIO_EXTS
                  | _MARKITDOWN_EXTS | _ARCHIVE_EXTS)

# Config-driven skip categories (v2): matched by NAME ONLY — the file is never read.
# With skip_media ON (the default) the non-deterministic media converters (OCR) never
# run, which is part of the determinism guarantee.
_VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v", ".wmv", ".flv", ".mpg", ".mpeg"}
_FONT_EXTS = {".otf", ".ttf", ".ttc", ".woff", ".woff2", ".eot"}
_GDRIVE_EXTS = {".gdoc", ".gsheet", ".gform", ".gdrive", ".gslides", ".gdraw", ".gmap", ".gsite"}
_JUNK_EXTS = {".tmp", ".ds_store", ".ini", ".lnk", ".crdownload", ".part"}
_JUNK_NAMES = {".ds_store", "thumbs.db", "desktop.ini", "icon\r"}


def _skip_category(path: Path, cfg: Config) -> str | None:
    """Return the skip category for ``path`` (or None to convert it). Name-based only."""
    ext = path.suffix.lower()
    name = path.name.lower()
    if getattr(cfg, "skip_media", True) and (
            ext in _IMAGE_EXTS or ext in _VIDEO_EXTS or ext in _AUDIO_EXTS):
        return "media"
    if getattr(cfg, "skip_fonts", True) and ext in _FONT_EXTS:
        return "font"
    if getattr(cfg, "skip_gdrive_pointers", True) and ext in _GDRIVE_EXTS:
        return "gdrive-pointer"
    if getattr(cfg, "skip_junk", True) and (ext in _JUNK_EXTS or name in _JUNK_NAMES):
        return "junk"
    return None


@dataclass
class ConvResult:
    source: str
    output: str | None = None
    status: str = "ok"          # ok | empty | unsupported | failed
    method: str = ""
    chars: int = 0
    error: str = ""

    def as_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if v != "" or k == "status"}


def _safe_out_name(src: Path, out_dir: Path) -> Path:
    # Keep the original extension in the name so foo.pdf and foo.docx don't clash.
    return out_dir / (src.name + ".md")


def _zip_within_bounds(path: Path, cfg: Config) -> bool:
    """Reject decompression bombs before MarkItDown extracts an archive.

    Skips archives whose total uncompressed size is excessive, or whose
    compression ratio is implausibly high. Non-zip or unreadable → allow (let the
    normal converter decide).
    """
    import zipfile
    if not zipfile.is_zipfile(path):
        return True
    try:
        with zipfile.ZipFile(path) as z:
            infos = z.infolist()
            total = sum(i.file_size for i in infos)
            comp = sum(i.compress_size for i in infos) or 1
        cap_mb = getattr(cfg, "max_file_mb", 0)
        if cap_mb and total > cap_mb * 4 * 1024 * 1024:   # uncompressed >> file cap
            return False
        if total / comp > 200:                            # extreme expansion ratio
            return False
        # Reject nested archives (classic recursive zip-bomb vector) — we can't
        # cheaply bound what an inner archive expands to.
        _nested = (".zip", ".gz", ".tgz", ".bz2", ".xz", ".7z", ".rar", ".tar")
        if any(i.filename.lower().endswith(_nested) for i in infos):
            return False
        return True
    except Exception:  # noqa: BLE001 — can't inspect → let the converter try
        return True


def _try_markitdown(path: Path, cfg: Config) -> tuple[str | None, str]:
    try:
        from markitdown import MarkItDown
    except Exception:
        return None, "markitdown-missing"
    # Legacy-Bengali pre-pass: if the Office file has Bijoy/SutonnyMJ-font runs, rewrite
    # them to Unicode in the OOXML first (font-aware; English untouched), then convert the
    # Unicode copy so MarkItDown's structure handling (tables, etc.) is preserved.
    src, suffix, converted = str(path), "markitdown", 0
    tmp = None
    if cfg.bangla_legacy:
        try:
            from .bangla_legacy import delegacify_to_temp
            tmp, converted = delegacify_to_temp(path)
            if tmp:
                src, suffix = tmp, "markitdown+bn-unicode"
        except Exception:  # noqa: BLE001 — legacy conversion must never break conversion
            tmp, src, suffix = None, str(path), "markitdown"
    try:
        md = MarkItDown(enable_plugins=False)
        res = md.convert(src)
        text = (res.text_content or "").strip()
        return (text or None), suffix
    except Exception as e:  # noqa: BLE001 — never let one file kill a batch
        return None, f"markitdown-error:{type(e).__name__}"
    finally:
        if tmp:
            try:
                os.unlink(tmp)
            except OSError:
                pass


def _tesseract_bin() -> str | None:
    import shutil
    from .platform import bootstrap_path
    bootstrap_path()
    return shutil.which("tesseract")


_OCR_LANGS: "frozenset[str] | None" = None


def _installed_ocr_langs() -> "frozenset[str]":
    """Tesseract language packs actually present on this machine (cached)."""
    global _OCR_LANGS
    if _OCR_LANGS is None:
        _OCR_LANGS = frozenset()
        tess = _tesseract_bin()
        if tess:
            import subprocess
            try:
                out = subprocess.run([tess, "--list-langs"], capture_output=True,
                                     timeout=15, text=True)
                # Line 0 is a header; the rest are language codes.
                _OCR_LANGS = frozenset(l.strip() for l in out.stdout.splitlines()[1:] if l.strip())
            except (OSError, subprocess.SubprocessError):
                _OCR_LANGS = frozenset()
    return _OCR_LANGS


def _resolve_ocr_lang(cfg: Config) -> str:
    """Keep only the requested OCR languages Tesseract actually has, so a default of
    ``eng+ben`` never errors on a machine that's missing the Bangla pack — it just
    drops to whatever's installed."""
    requested = [c for c in (cfg.ocr_lang or "eng").split("+") if c.strip()]
    installed = _installed_ocr_langs()
    if not installed:                       # couldn't enumerate → trust the request
        return "+".join(requested) or "eng"
    keep = [c for c in requested if c in installed]
    if not keep:
        keep = ["eng"] if "eng" in installed else sorted(installed)[:1]
    return "+".join(keep) or "eng"


def _ocr_image_bytes(png_bytes: bytes, cfg: Config) -> str | None:
    """OCR via piping PNG bytes to `tesseract stdin stdout` — no temp files.

    The temp-file path pytesseract uses by default breaks under sandboxed/sparse
    environments; piping is robust everywhere and supports PSM 1 auto-orientation.
    """
    import subprocess
    tess = _tesseract_bin()
    if not tess:
        return None
    lang = _resolve_ocr_lang(cfg)
    try:
        proc = subprocess.run([tess, "stdin", "stdout", "-l", lang, "--psm", "1"],
                              input=png_bytes, capture_output=True, timeout=180)
        return (proc.stdout.decode("utf-8", "replace").strip() or None)
    except (OSError, subprocess.SubprocessError):
        return None


def _try_ocr(path: Path, cfg: Config) -> tuple[str | None, str]:
    if not _tesseract_bin():
        return None, "ocr-missing"
    try:
        import io

        from PIL import Image
        with Image.open(path) as im:
            buf = io.BytesIO()
            im.convert("RGB").save(buf, format="PNG")
        text = _ocr_image_bytes(buf.getvalue(), cfg)
        return text, "tesseract"
    except Exception as e:  # noqa: BLE001
        return None, f"ocr-error:{type(e).__name__}"


def _ocr_pdf(path: Path, cfg: Config, max_pages: int = 50) -> tuple[str | None, str]:
    """OCR a scanned/image-only PDF by rasterising pages with pypdfium2."""
    if not _tesseract_bin():
        return None, "ocr-missing"
    try:
        import io

        import pypdfium2 as pdfium
    except Exception:
        return None, "pdf-ocr-missing"
    pdf = None
    try:
        pdf = pdfium.PdfDocument(str(path))
        pages = []
        for i in range(min(len(pdf), max_pages)):
            bitmap = pdf[i].render(scale=2.0)
            pil = bitmap.to_pil()
            buf = io.BytesIO()
            pil.convert("RGB").save(buf, format="PNG")
            txt = _ocr_image_bytes(buf.getvalue(), cfg)
            if txt:
                pages.append(txt)
        joined = "\n\n".join(pages).strip()
        return (joined or None), "tesseract-pdf"
    except Exception as e:  # noqa: BLE001
        return None, f"pdf-ocr-error:{type(e).__name__}"
    finally:
        if pdf is not None:
            try:
                pdf.close()
            except Exception:  # noqa: BLE001
                pass


# Byte-order marks for the Unicode encodings a Windows editor commonly writes. UTF-32
# must precede UTF-16 (the UTF-16-LE BOM is a prefix of the UTF-32-LE BOM).
_BOMS = (
    (b"\xef\xbb\xbf", "utf-8-sig"),
    (b"\xff\xfe\x00\x00", "utf-32-le"), (b"\x00\x00\xfe\xff", "utf-32-be"),
    (b"\xff\xfe", "utf-16-le"), (b"\xfe\xff", "utf-16-be"),
)


def _decode_text_bytes(raw: bytes) -> str:
    """Decode bytes to text honoring a Unicode BOM (UTF-8/16/32 — what Windows editors
    write for 'Unicode' .txt/.csv), else UTF-8 with replacement. Always returns a str.

    Reading a UTF-16 file as UTF-8 yields mojibake, and its interleaved NUL bytes used
    to get the file misclassified as binary — this fixes both."""
    for bom, codec in _BOMS:
        if raw.startswith(bom):
            try:
                # Explicit-endian utf-16/32 codecs KEEP the leading U+FEFF; strip it so
                # it can't prepend a zero-width char to the first heading/entity. (utf-8-sig
                # already strips its BOM; lstrip is then a harmless no-op.)
                return raw.decode(codec, errors="replace").lstrip("\ufeff")
            except (LookupError, UnicodeError):
                break
    return raw.decode("utf-8", errors="replace")


def _native_text(path: Path) -> tuple[str | None, str]:
    try:
        raw = _decode_text_bytes(path.read_bytes()).strip()   # BOM/UTF-16-aware
    except OSError as e:
        return None, f"read-error:{type(e).__name__}"
    ext = path.suffix.lower()
    if ext in _TEXT_EXTS:
        return (raw or None), "text-passthrough"
    # Lightly fence structured data so it reads as markdown.
    lang = {".json": "json", ".ndjson": "json", ".xml": "xml",
            ".yaml": "yaml", ".yml": "yaml"}.get(ext, "")
    if ext in (".csv", ".tsv"):
        return (raw or None), "data-passthrough"
    body = f"```{lang}\n{raw}\n```" if raw else ""
    return (body or None), "data-passthrough"


def _try_unknown_text(path: Path) -> tuple[str | None, str]:
    """Best-effort digest of an unknown extension as plain text, so nothing textual
    is silently skipped (source code, .log, .ini, .tex, .org, …). Genuine binaries
    (NUL bytes / mostly non-printable) return None → 'unsupported'. UTF-8 multibyte
    text (e.g. Bangla) is preserved — high bytes count as text, not binary."""
    try:
        with open(path, "rb") as f:
            chunk = f.read(65536)
    except OSError as e:
        return None, f"read-error:{type(e).__name__}"
    if not chunk:
        return None, "empty"
    bom = next((c for b, c in _BOMS if chunk.startswith(b)), None)
    if bom is None:
        # No BOM: a NUL byte or mostly-control content means a genuine binary. (A BOM'd
        # UTF-16 file legitimately contains NULs, so it skips this and decodes below.)
        if b"\x00" in chunk:
            return None, "binary"
        printable = sum(1 for b in chunk if 9 <= b <= 13 or 32 <= b <= 126 or b >= 128)
        if printable / len(chunk) < 0.85:
            return None, "binary"
    try:
        raw = _decode_text_bytes(path.read_bytes()).strip()   # BOM/UTF-16-aware
    except OSError as e:
        return None, f"read-error:{type(e).__name__}"
    return (raw or None), ("text-fallback-bom" if bom else "text-fallback")


def convert_file(path: Path, out_dir: Path, cfg: Config,
                 out_name: str | None = None) -> ConvResult:
    """Convert a single file to a Markdown file on disk. Returns metadata only."""
    path = Path(path)
    out_dir.mkdir(parents=True, exist_ok=True)
    res = ConvResult(source=str(path))
    if not path.exists() or not path.is_file():
        res.status, res.error = "failed", "not-a-file"
        return res

    # v2 skip filter (media/fonts/gdrive-pointers/junk): name-based, never reads the
    # file, and wins over every other classification. status='skipped' so digest
    # stats count them honestly (never 'unsupported'/'failed').
    cat = _skip_category(path, cfg)
    if cat:
        res.status, res.method, res.error = "skipped", "skipped-type", cat
        return res

    # A 0-byte file (placeholder, touch'd, failed download) is "empty" — a clear,
    # honest status — never "unsupported"/"failed", regardless of its extension.
    try:
        if path.stat().st_size == 0:
            res.status, res.method = "empty", "empty-file"
            return res
    except OSError:
        pass

    # Bound memory: skip oversize files before reading them in.
    cap = getattr(cfg, "max_file_mb", 0)
    if cap and cap > 0:
        try:
            if path.stat().st_size > cap * 1024 * 1024:
                res.status, res.method, res.error = "skipped", "too-large", f">{cap}MB"
                return res
        except OSError:
            pass

    ext = path.suffix.lower()
    text: str | None = None
    method = ""

    if _archive_kind(path) is not None:
        # Archives are expanded at the digest level (archive.py). One reaching the
        # converter means expansion was off, unavailable (no rar/7z tool), corrupt,
        # or over budget → honest skip, never a crash.
        res.status, res.method, res.error = "skipped", "archive", "not-expanded"
        return res

    if ext in _TEXT_EXTS or ext in _DATA_EXTS:
        text, method = _native_text(path)
    elif ext in _MARKITDOWN_EXTS:
        # OOXML/EPUB (.docx/.xlsx/.pptx/.epub) and .zip are ALL zip containers —
        # bomb-check every one, not just literal .zip (SEC-01). _zip_within_bounds
        # no-ops on non-zip inputs (.pdf/.html/.xls/.doc/.msg), so this is safe.
        if not _zip_within_bounds(path, cfg):
            res.status, res.method, res.error = "skipped", "zip-too-large", "decompression-bound"
            return res
        text, method = _try_markitdown(path, cfg)
        if not text and ext == ".pdf" and cfg.ocr_mode != "off":  # scanned PDF → OCR
            text, method = _ocr_pdf(path, cfg)
    elif ext in _IMAGE_EXTS:
        if cfg.ocr_mode != "off":
            text, method = _try_ocr(path, cfg)
    elif ext in _AUDIO_EXTS:
        text, method = None, "audio-unsupported"   # model-free: audio transcription dropped in v2
    else:
        # No/unknown extension: content-sniff first. ZIP magic (PK\x03\x04) usually
        # means a misnamed Office file (an .xlsx/.docx saved without its extension) —
        # MarkItDown sniffs the real type from content, so give it a shot (bomb-checked)
        # before the plain-text fallback.
        head = b""
        try:
            with open(path, "rb") as f:
                head = f.read(4)
        except OSError:
            pass
        if head == b"PK\x03\x04":
            if not _zip_within_bounds(path, cfg):
                res.status, res.method, res.error = "skipped", "zip-too-large", "decompression-bound"
                return res
            text, method = _try_markitdown(path, cfg)
            if text:
                method = method + "+sniffed-zip"
        if text is None:
            # Digest as plain text when the content looks textual; genuine binaries
            # stay 'unsupported'.
            text, method = _try_unknown_text(path)
        if text is None:
            res.status, res.method, res.error = "unsupported", ext or "no-ext", method
            return res

    res.method = method
    if text is None:
        # Distinguish "tool missing/errored" (failed) from "ran but empty".
        res.status = "failed" if any(x in method for x in
                                     ("missing", "error", "unavailable")) else "empty"
        if res.status == "failed":
            res.error = method
        return res

    # Plain-text legacy-Bengali safety net (Office is handled font-aware in _try_markitdown;
    # OCR/vision/whisper already emit Unicode, so density-gated maybe_convert is a no-op there).
    if cfg.bangla_legacy and "markitdown" not in method:
        from .bangla_legacy import maybe_convert
        text, _bn = maybe_convert(text)
        if _bn:
            method = res.method = method + "+bn-unicode"

    out = (out_dir / out_name) if out_name else _safe_out_name(path, out_dir)
    header = f"<!-- source: {path.name} · method: {method} -->\n\n"
    out.write_text(header + text, encoding="utf-8")
    res.output = str(out)
    res.chars = len(text)
    res.status = "ok"
    return res
