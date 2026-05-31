"""Local, token-free conversion of any attachment to Markdown.

Conversion order of preference for each file:
  1. Native passthrough for text/markdown/csv/json/xml (no dependency needed).
  2. Microsoft **MarkItDown** (latest, auto-updated) for PDF/Office/HTML/EPub/…
  3. **Tesseract** OCR for images and scanned/image-only PDFs.
  4. **Whisper** (Apple-MLX accelerated on arm64, faster-whisper fallback) for audio.
  5. Local **Ollama vision** captioning for images OCR can't read.

Every converter runs entirely on-device. The function returns only metadata
(paths, sizes, status) — never file content — so a whole folder costs ~0 tokens.
Missing optional dependencies degrade to a clear ``unsupported``/``empty`` status
rather than crashing a batch.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from .config import Config
from .lifecycle import OllamaManager

# File-type groupings.
_TEXT_EXTS = {".txt", ".md", ".markdown", ".text", ".log", ".rst"}
_DATA_EXTS = {".csv", ".tsv", ".json", ".xml", ".yaml", ".yml", ".ndjson"}
_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tiff", ".tif", ".webp"}
_AUDIO_EXTS = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".aac"}
_MARKITDOWN_EXTS = {".pdf", ".docx", ".pptx", ".xlsx", ".xls", ".html", ".htm",
                    ".epub", ".msg", ".rtf", ".doc", ".ppt", ".zip"}
SUPPORTED_EXTS = (_TEXT_EXTS | _DATA_EXTS | _IMAGE_EXTS | _AUDIO_EXTS
                  | _MARKITDOWN_EXTS)


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


def _try_markitdown(path: Path, cfg: Config) -> tuple[str | None, str]:
    try:
        from markitdown import MarkItDown
    except Exception:
        return None, "markitdown-missing"
    try:
        md = MarkItDown(enable_plugins=False)
        res = md.convert(str(path))
        text = (res.text_content or "").strip()
        return (text or None), "markitdown"
    except Exception as e:  # noqa: BLE001 — never let one file kill a batch
        return None, f"markitdown-error:{type(e).__name__}"


def _try_ocr(path: Path, cfg: Config) -> tuple[str | None, str]:
    try:
        import pytesseract
        from PIL import Image
    except Exception:
        return None, "ocr-missing"
    try:
        with Image.open(path) as im:
            text = pytesseract.image_to_string(im, lang=cfg.ocr_lang or "eng")
        text = (text or "").strip()
        return (text or None), "tesseract"
    except Exception as e:  # noqa: BLE001
        return None, f"ocr-error:{type(e).__name__}"


def _try_vision(path: Path, cfg: Config, ollama: OllamaManager) -> tuple[str | None, str]:
    if cfg.vision_mode == "off":
        return None, "vision-off"
    if not ollama.ensure_running(wait=20):
        return None, "vision-unavailable"
    import base64
    import urllib.request
    try:
        b64 = base64.b64encode(path.read_bytes()).decode()
        payload = json.dumps({
            "model": cfg.vision_model,
            "prompt": "Describe this image.",
            "images": [b64],
            "stream": False,
        }).encode()
        req = urllib.request.Request(f"{ollama.host}/api/generate", data=payload,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.loads(r.read())
        ollama.touch()
        text = (data.get("response") or "").strip()
        return (text or None), "ollama-vision"
    except Exception as e:  # noqa: BLE001
        return None, f"vision-error:{type(e).__name__}"


def _try_whisper(path: Path, cfg: Config) -> tuple[str | None, str]:
    if cfg.transcribe_mode == "off":
        return None, "transcribe-off"
    from .platform import mlx_available
    # Apple MLX (GPU) first.
    if mlx_available():
        try:
            import mlx_whisper
            repo = f"mlx-community/whisper-{cfg.whisper_model}-mlx"
            res = mlx_whisper.transcribe(str(path), path_or_hf_repo=repo)
            text = (res.get("text") or "").strip()
            return (text or None), "mlx-whisper"
        except Exception:  # noqa: BLE001 — fall through to CPU
            pass
    try:
        from faster_whisper import WhisperModel
        model = WhisperModel(cfg.whisper_model, device="cpu", compute_type="int8")
        segments, _ = model.transcribe(str(path))
        text = " ".join(s.text for s in segments).strip()
        return (text or None), "faster-whisper"
    except Exception as e:  # noqa: BLE001
        return None, f"transcribe-error:{type(e).__name__}"


def _native_text(path: Path) -> tuple[str | None, str]:
    try:
        raw = path.read_text(encoding="utf-8", errors="replace").strip()
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


def convert_file(path: Path, out_dir: Path, cfg: Config,
                 ollama: OllamaManager | None = None) -> ConvResult:
    """Convert a single file to a Markdown file on disk. Returns metadata only."""
    path = Path(path)
    out_dir.mkdir(parents=True, exist_ok=True)
    res = ConvResult(source=str(path))
    if not path.exists() or not path.is_file():
        res.status, res.error = "failed", "not-a-file"
        return res

    ext = path.suffix.lower()
    text: str | None = None
    method = ""

    if ext in _TEXT_EXTS or ext in _DATA_EXTS:
        text, method = _native_text(path)
    elif ext in _MARKITDOWN_EXTS:
        text, method = _try_markitdown(path, cfg)
        if not text and ext == ".pdf":      # scanned PDF → OCR
            text, method = _try_ocr(path, cfg)
    elif ext in _IMAGE_EXTS:
        if cfg.ocr_mode != "off":
            text, method = _try_ocr(path, cfg)
        if not text and cfg.vision_mode != "off":
            text, method = _try_vision(path, cfg, ollama or OllamaManager(cfg))
    elif ext in _AUDIO_EXTS:
        text, method = _try_whisper(path, cfg)
    else:
        res.status, res.method = "unsupported", ext or "no-ext"
        return res

    res.method = method
    if text is None:
        # Distinguish "tool missing/errored" (failed) from "ran but empty".
        res.status = "failed" if any(x in method for x in
                                     ("missing", "error", "unavailable")) else "empty"
        if res.status == "failed":
            res.error = method
        return res

    out = _safe_out_name(path, out_dir)
    header = f"<!-- source: {path.name} · method: {method} -->\n\n"
    out.write_text(header + text, encoding="utf-8")
    res.output = str(out)
    res.chars = len(text)
    res.status = "ok"
    return res
