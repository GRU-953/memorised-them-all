"""Configuration — read entirely from the environment with safe defaults.

Every heavy knob is here so the rest of the engine stays declarative. Nothing in
this module reaches the network or the model stack; it only resolves paths and
reads ``MTA_*`` environment variables.
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


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", name.strip()).strip("-_.")
    return (slug.lower() or "default")[:120]  # cap so the dir name never exceeds FS limits


@dataclass
class Config:
    """Resolved runtime configuration for one engine invocation."""

    home: Path = field(default_factory=lambda: Path(
        _env("MTA_HOME", str(Path.home() / ".memorised-them-all"))).expanduser())

    # Models (all local / Ollama).
    extract_model: str = field(default_factory=lambda: _env("MTA_EXTRACT_MODEL", "qwen2.5:7b"))
    embed_model: str = field(default_factory=lambda: _env("MTA_EMBED_MODEL", "nomic-embed-text"))
    vision_model: str = field(default_factory=lambda: _env("MTA_VISION_MODEL", "moondream"))
    whisper_model: str = field(default_factory=lambda: _env("MTA_WHISPER_MODEL", "base"))

    # Conversion.
    ocr_lang: str = field(default_factory=lambda: _env("MTA_OCR_LANG", "eng"))
    ocr_mode: str = field(default_factory=lambda: _env("MTA_OCR", "auto"))        # auto|off|force|hybrid
    vision_mode: str = field(default_factory=lambda: _env("MTA_VISION", "auto"))   # auto|off|force
    transcribe_mode: str = field(default_factory=lambda: _env("MTA_TRANSCRIBE", "auto"))  # auto|off

    # Extraction / digestion.
    extract_mode: str = field(default_factory=lambda: _env("MTA_EXTRACT", "auto"))  # auto|llm|classical
    # Fast mode: skip the LLM entirely (classical extraction + deterministic
    # summaries), keeping the small embedding model for recall. Opt-in; the
    # default stays the accurate LLM path.
    fast: bool = field(default_factory=lambda: _env("MTA_FAST", "off").lower()
                       in ("on", "1", "true", "yes"))
    community_algo: str = field(default_factory=lambda: _env("MTA_COMMUNITY_ALGO", "auto"))  # auto|leiden|louvain|greedy
    chunk_chars: int = field(default_factory=lambda: _env_int("MTA_CHUNK_CHARS", 1200))
    recall_k: int = field(default_factory=lambda: _env_int("MTA_RECALL_K", 8))
    # Absolute cosine floor for recall hits (real embeddings only). 0 = off
    # (return all top-k); raise it (e.g. 0.45) for stricter grounding.
    recall_min_score: float = field(default_factory=lambda: _env_float("MTA_RECALL_MIN_SCORE", 0.0))
    max_chunks: int = field(default_factory=lambda: _env_int("MTA_MAX_CHUNKS", 1500))
    # Skip individual files larger than this (MB) before reading them into memory,
    # bounding OOM/decompression-bomb risk. 0 disables the cap.
    max_file_mb: int = field(default_factory=lambda: _env_int("MTA_MAX_FILE_MB", 200))
    extract_workers: int = field(default_factory=lambda: _env_int("MTA_EXTRACT_WORKERS", 0))  # 0=auto

    # Lifecycle & maintenance.
    idle_seconds: int = field(default_factory=lambda: _env_int("MTA_IDLE", 300))
    auto_update: bool = field(default_factory=lambda: _env("MTA_AUTO_UPDATE", "on").lower()
                              not in ("off", "0", "false", "no"))
    # MarkItDown update source: PyPI (default — pinned, offline-correct, pip-verified)
    # or the latest UPSTREAM commit (opt-in, pinned to a resolved SHA). Enable with
    # MTA_AUTO_UPDATE=upstream or MTA_MARKITDOWN_UPSTREAM=on.
    markitdown_upstream: bool = field(default_factory=lambda:
                              _env("MTA_AUTO_UPDATE", "on").strip().lower() == "upstream"
                              or _env("MTA_MARKITDOWN_UPSTREAM", "off").strip().lower()
                              in ("on", "1", "true", "yes"))
    ollama_host: str = field(default_factory=lambda: _env("OLLAMA_HOST", "http://127.0.0.1:11434"))

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
    def mindmap_html(self) -> Path:
        return self.project_dir / "mindmap.html"

    @property
    def state_dir(self) -> Path:
        return self.home / "state"

    def ensure_dirs(self) -> None:
        for d in (self.projects_dir, self.project_dir, self.markdown_dir,
                  self.memory_dir, self.state_dir):
            d.mkdir(parents=True, exist_ok=True)


def load() -> Config:
    cfg = Config()
    if cfg.fast:
        cfg.extract_mode = "classical"  # no LLM extraction or summaries
    return cfg
