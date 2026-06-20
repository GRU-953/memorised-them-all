"""Configuration — read entirely from the environment with safe defaults.

Every heavy knob is here so the rest of the engine stays declarative. Nothing in
this module reaches the network or any model stack; v2 is **fully deterministic and
model-free** (no Ollama, no embedding model, no GPU, no network). It only resolves
paths and reads ``MTA_*`` environment variables.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path


def _env(name: str, default: str) -> str:
    val = os.environ.get(name)
    return val if val not in (None, "") else default


def _env_int(name: str, default: int) -> int:
    try:
        return int(str(os.environ.get(name, default)).strip())
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(str(os.environ.get(name, default)).strip())
    except (TypeError, ValueError):
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw in (None, ""):
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", name.strip()).strip("-_.")
    return (slug.lower() or "default")[:120]  # cap so the dir name never exceeds FS limits


def _resolve_home() -> Path:
    """Resolve ``MTA_HOME`` robustly.

    Some launchers — notably MCPB / Claude Desktop manifest substitution — can pass
    an **unexpanded** value such as ``${HOME}/.memorised-them-all``. We expand
    ``$VAR`` / ``${VAR}`` and ``~`` ourselves; if a placeholder still survives, or the
    result isn't an absolute path, fall back to the safe default instead of writing to
    a bogus literal directory (which silently broke ``digest`` and left
    ``config_file`` null)."""
    raw = _env("MTA_HOME", "").strip()
    if raw:
        cand = Path(os.path.expanduser(os.path.expandvars(raw)))
        if cand.is_absolute() and "$" not in str(cand):
            return cand
    return Path.home() / ".memorised-them-all"


@dataclass
class Config:
    """Resolved runtime configuration for one engine invocation (deterministic, model-free)."""

    home: Path = field(default_factory=_resolve_home)

    # Auto-convert legacy Bengali (Bijoy/SutonnyMJ ANSI fonts) → Unicode during file
    # conversion (font-aware for Office, density-gated for plain text). Default on.
    bangla_legacy: bool = field(default_factory=lambda: _env_bool("MTA_BANGLA_LEGACY", True))

    # Conversion (offline). OCR via Tesseract is OPTIONAL and offline; English + Bangla
    # by default. Missing Tesseract language packs are dropped gracefully at OCR time.
    # ocr_mode auto|off|force|hybrid — but with skip_media ON (the default) images are
    # skipped before OCR ever runs, so OCR only applies when a user opts media back in.
    ocr_lang: str = field(default_factory=lambda: _env("MTA_OCR_LANG", "eng+ben"))
    ocr_mode: str = field(default_factory=lambda: _env("MTA_OCR", "auto"))        # auto|off|force|hybrid

    # Corpus skip switches (default ON). They keep the digest deterministic and lean:
    # media (images/video/audio) and fonts/Google-Drive-pointer-stubs/junk are skipped
    # WITHOUT reading the file. Turning skip_media off re-enables the optional, NON-
    # deterministic converters (Tesseract OCR) — at the cost of the determinism guarantee.
    skip_media: bool = field(default_factory=lambda: _env_bool("MTA_SKIP_MEDIA", True))
    skip_fonts: bool = field(default_factory=lambda: _env_bool("MTA_SKIP_FONTS", True))
    skip_gdrive_pointers: bool = field(default_factory=lambda: _env_bool("MTA_SKIP_GDRIVE", True))
    skip_junk: bool = field(default_factory=lambda: _env_bool("MTA_SKIP_JUNK", True))

    # Recursive archive expansion (default ON): unpack zip/tar/gz/bz2/xz (+ optional
    # rar/7z) and digest their contents, with bomb/quine/path-traversal guards.
    archive_recursive: bool = field(default_factory=lambda: _env_bool("MTA_ARCHIVE_RECURSIVE", True))
    archive_max_depth: int = field(default_factory=lambda: max(1, _env_int("MTA_ARCHIVE_DEPTH", 8)))
    archive_max_entries: int = field(default_factory=lambda: max(1, _env_int("MTA_ARCHIVE_ENTRIES", 100000)))

    # Digest ALL file types: when on (default), a folder/glob digest also picks up unknown
    # extensions (digested as text when textual; binaries skipped). Hidden files/dirs (.*)
    # are still skipped. Off → only the known SUPPORTED_EXTS are collected.
    digest_all: bool = field(default_factory=lambda: _env_bool("MTA_DIGEST_ALL", True))
    community_algo: str = field(default_factory=lambda: _env("MTA_COMMUNITY_ALGO", "auto"))  # auto|leiden|louvain|greedy
    chunk_chars: int = field(default_factory=lambda: _env_int("MTA_CHUNK_CHARS", 1200))
    recall_k: int = field(default_factory=lambda: _env_int("MTA_RECALL_K", 8))
    # Absolute BM25-score floor for recall hits (unbounded ≥0, NOT a 0–1 cosine). 0 = off
    # (return all top-k), the default — relevance is gated by lexical overlap (DOC-01).
    # Set MTA_RECALL_MIN_SCORE on the BM25 scale (scores routinely exceed 1).
    recall_min_score: float = field(default_factory=lambda: _env_float("MTA_RECALL_MIN_SCORE", 0.0))
    max_chunks: int = field(default_factory=lambda: _env_int("MTA_MAX_CHUNKS", 1500))
    # Skip individual files larger than this (MB) before reading them into memory,
    # bounding OOM/decompression-bomb risk. 0 disables the cap.
    max_file_mb: int = field(default_factory=lambda: max(0, _env_int("MTA_MAX_FILE_MB", 200)))
    extract_workers: int = field(default_factory=lambda: _env_int("MTA_EXTRACT_WORKERS", 0))  # 0=auto
    # Per-file conversion timeout (seconds): each file converts in its own killable
    # subprocess, so one pathological file (a parser that hangs forever) can never stall
    # the whole batch. Scaled up by file size; capped at convert_timeout_max. 0 disables.
    convert_timeout: int = field(default_factory=lambda: max(0, _env_int("MTA_CONVERT_TIMEOUT", 120)))
    convert_timeout_max: int = field(default_factory=lambda: max(0, _env_int("MTA_CONVERT_TIMEOUT_MAX", 900)))

    # Maintenance.
    auto_update: bool = field(default_factory=lambda: _env("MTA_AUTO_UPDATE", "on").lower()
                              not in ("off", "0", "false", "no"))
    # MarkItDown update source: PyPI (default — pinned, offline-correct, pip-verified)
    # or the latest UPSTREAM commit (opt-in, pinned to a resolved SHA). Enable with
    # MTA_AUTO_UPDATE=upstream or MTA_MARKITDOWN_UPSTREAM=on.
    markitdown_upstream: bool = field(default_factory=lambda:
                              _env("MTA_AUTO_UPDATE", "on").strip().lower() == "upstream"
                              or _env_bool("MTA_MARKITDOWN_UPSTREAM", False))

    # Remote / HTTP transport (opt-in; the default transport stays stdio). The
    # server binds to loopback only unless http_allow_remote is set, and every
    # request must carry a bearer token (auto-generated + persisted 0600 when
    # http_token is empty). These are just resolved values — nothing here opens a
    # socket; mta/transport.py consumes them. See SECURITY.md.
    http_host: str = field(default_factory=lambda: _env("MTA_HTTP_HOST", "127.0.0.1"))
    http_port: int = field(default_factory=lambda: _env_int("MTA_HTTP_PORT", 8765))
    http_path: str = field(default_factory=lambda: "/" + _env("MTA_HTTP_PATH", "/mcp").strip().lstrip("/"))
    http_token: str = field(default_factory=lambda: _env("MTA_HTTP_TOKEN", "").strip())
    http_allow_remote: bool = field(default_factory=lambda: _env_bool("MTA_HTTP_ALLOW_REMOTE", False))
    # Extra comma-separated hosts/origins added to the DNS-rebinding allowlist
    # (the bound host:port + localhost are always included). For reverse-proxy use.
    http_allowed_hosts: str = field(default_factory=lambda: _env("MTA_HTTP_ALLOWED_HOSTS", "").strip())
    http_allowed_origins: str = field(default_factory=lambda: _env("MTA_HTTP_ALLOWED_ORIGINS", "").strip())

    # Parallelism (0/auto → decided by platform tuning).
    workers: int = field(default_factory=lambda: _env_int("MTA_WORKERS", 0))

    # The active project (a named, reusable memory).
    project: str = field(default_factory=lambda: _slugify(_env("MTA_PROJECT", "default")))

    def with_project(self, name: str | None) -> "Config":
        if name:
            self.project = _slugify(name)
        return self

    # ---- Path helpers -------------------------------------------------
    @property
    def projects_dir(self) -> Path:
        return self.home / "projects"

    @property
    def project_dir(self) -> Path:
        return self.projects_dir / self.project

    @property
    def markdown_dir(self) -> Path:
        return self.project_dir / "markdown"

    @property
    def memory_dir(self) -> Path:
        return self.project_dir / "memory"

    @property
    def graph_path(self) -> Path:
        return self.project_dir / "graph.json"

    @property
    def vectors_path(self) -> Path:
        return self.project_dir / "vectors.npz"

    @property
    def memory_md(self) -> Path:
        return self.project_dir / "memory.md"

    @property
    def unpack_dir(self) -> Path:
        """Scratch root for recursively-expanded archive contents (under the project,
        in the MAIN process — never an mkdtemp inside a killable convert child)."""
        return self.project_dir / "_unpacked"

    @property
    def state_dir(self) -> Path:
        return self.home / "state"

    @property
    def http_token_file(self) -> Path:
        """Where an auto-generated HTTP bearer token is persisted (0600)."""
        return self.state_dir / "http_token"

    def ensure_dirs(self) -> None:
        for d in (self.projects_dir, self.project_dir, self.markdown_dir,
                  self.memory_dir, self.state_dir):
            d.mkdir(parents=True, exist_ok=True)


def persist_config(cfg: "Config") -> Path:
    """Write the resolved knobs to ``state/config.json`` — a readable record of
    what the engine actually resolved (surfaced by ``mta status`` / doctor). Atomic."""
    import json
    import tempfile
    cfg.state_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "engine": "deterministic", "model_free": True, "home": str(cfg.home),
        "ocr_lang": cfg.ocr_lang, "ocr_mode": cfg.ocr_mode,
        "skip_media": cfg.skip_media, "skip_fonts": cfg.skip_fonts,
        "skip_gdrive_pointers": cfg.skip_gdrive_pointers, "skip_junk": cfg.skip_junk,
        "archive_recursive": cfg.archive_recursive, "archive_max_depth": cfg.archive_max_depth,
        "archive_max_entries": cfg.archive_max_entries,
        "auto_update": cfg.auto_update, "markitdown_upstream": cfg.markitdown_upstream,
        "workers": cfg.workers, "extract_workers": cfg.extract_workers,
        "recall_k": cfg.recall_k, "recall_min_score": cfg.recall_min_score,
        "max_chunks": cfg.max_chunks, "max_file_mb": cfg.max_file_mb,
        "convert_timeout": cfg.convert_timeout,
    }
    path = cfg.state_dir / "config.json"
    fd, tmp = tempfile.mkstemp(dir=str(cfg.state_dir), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return path


def load() -> Config:
    """Resolve config from the environment. v2 is model-free and profile-free — there
    are no models/Ollama to size, so this is just ``Config()`` (every knob has an env
    default). Kept as a function so callers/imports stay stable."""
    return Config()
