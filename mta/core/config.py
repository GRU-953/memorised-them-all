"""Configuration — read entirely from the environment with safe defaults.

Every heavy knob is here so the rest of the engine stays declarative. Nothing in
this module reaches the network or the model stack; it only resolves paths and
reads ``MTA_*`` environment variables.
"""
from __future__ import annotations

import os
import re
import threading
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
    # Hard offline switch (also set by the 'offline' profile). Resolved here so the
    # whole engine — including the Ollama lifecycle — consults one flag.
    no_ollama: bool = field(default_factory=lambda: _env("MTA_NO_OLLAMA", "off").strip().lower()
                            in ("1", "true", "yes", "on"))
    ollama_host: str = field(default_factory=lambda: _env("OLLAMA_HOST", "http://127.0.0.1:11434"))

    # Remote / HTTP transport (opt-in; the default transport stays stdio). The
    # server binds to loopback only unless http_allow_remote is set, and every
    # request must carry a bearer token (auto-generated + persisted 0600 when
    # http_token is empty). These are just resolved values — nothing here opens a
    # socket; mta/transport.py consumes them. See SECURITY.md.
    http_host: str = field(default_factory=lambda: _env("MTA_HTTP_HOST", "127.0.0.1"))
    http_port: int = field(default_factory=lambda: _env_int("MTA_HTTP_PORT", 8765))
    http_path: str = field(default_factory=lambda: "/" + _env("MTA_HTTP_PATH", "/mcp").strip().lstrip("/"))
    http_token: str = field(default_factory=lambda: _env("MTA_HTTP_TOKEN", "").strip())
    http_allow_remote: bool = field(default_factory=lambda: _env("MTA_HTTP_ALLOW_REMOTE", "off")
                                    .strip().lower() in ("1", "true", "yes", "on"))
    # Extra comma-separated hosts/origins added to the DNS-rebinding allowlist
    # (the bound host:port + localhost are always included). For reverse-proxy use.
    http_allowed_hosts: str = field(default_factory=lambda: _env("MTA_HTTP_ALLOWED_HOSTS", "").strip())
    http_allowed_origins: str = field(default_factory=lambda: _env("MTA_HTTP_ALLOWED_ORIGINS", "").strip())

    # Parallelism (0/auto → decided by platform tuning).
    workers: int = field(default_factory=lambda: _env_int("MTA_WORKERS", 0))

    # The active project (a named, reusable memory).
    project: str = field(default_factory=lambda: _slugify(_env("MTA_PROJECT", "default")))
    # Active tuning profile (resolved in load(); see PROFILES).
    profile_name: str = "default"

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

    @property
    def http_token_file(self) -> Path:
        """Where an auto-generated HTTP bearer token is persisted (0600)."""
        return self.state_dir / "http_token"

    def ensure_dirs(self) -> None:
        for d in (self.projects_dir, self.project_dir, self.markdown_dir,
                  self.memory_dir, self.state_dir):
            d.mkdir(parents=True, exist_ok=True)


# Named profiles: bundles of MTA_* defaults applied when MTA_PROFILE is set. An
# explicit env var always wins (env > profile > built-in default).
PROFILES: dict = {
    "offline":     {"MTA_NO_OLLAMA": "1", "MTA_EXTRACT": "classical", "MTA_AUTO_UPDATE": "off"},
    "laptop":      {"MTA_EXTRACT_WORKERS": "1"},
    "workstation": {"MTA_EXTRACT_WORKERS": "2"},
    "server":      {"MTA_EXTRACT_WORKERS": "3", "MTA_AUTO_UPDATE": "off"},
}


def persist_config(cfg: "Config") -> Path:
    """Write the resolved knobs to ``state/config.json`` — a readable record of
    what the engine actually resolved (surfaced by ``mta status`` / doctor). Atomic."""
    import json
    import tempfile
    cfg.state_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "profile": cfg.profile_name, "home": str(cfg.home),
        "extract_model": cfg.extract_model, "embed_model": cfg.embed_model,
        "vision_model": cfg.vision_model, "whisper_model": cfg.whisper_model,
        "ocr_lang": cfg.ocr_lang, "extract_mode": cfg.extract_mode, "fast": cfg.fast,
        "idle_seconds": cfg.idle_seconds, "auto_update": cfg.auto_update,
        "markitdown_upstream": cfg.markitdown_upstream, "no_ollama": cfg.no_ollama,
        "workers": cfg.workers, "extract_workers": cfg.extract_workers,
        "recall_k": cfg.recall_k, "recall_min_score": cfg.recall_min_score,
        "max_chunks": cfg.max_chunks, "max_file_mb": cfg.max_file_mb,
    }
    path = cfg.state_dir / "config.json"
    fd, tmp = tempfile.mkstemp(dir=str(cfg.state_dir), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return path


# Serialises the profile seed→construct→restore window below: that mutates
# process-global os.environ, so concurrent load() calls (e.g. parallel digests or
# the recall/extract thread pools) must not observe each other's temporary keys —
# otherwise a parallel load under MTA_PROFILE=offline could resolve no_ollama=False.
_LOAD_LOCK = threading.Lock()


def load() -> Config:
    # Apply a named profile (if any) by seeding its MTA_* defaults — but only where
    # the user hasn't set them (env > profile > built-in). The seeded keys are
    # captured into the Config, then removed so the process env isn't mutated for
    # other components / subprocesses. Only the (rare) profile path touches the
    # global env, and it's serialised; the common no-profile path is lock-free.
    profile = _env("MTA_PROFILE", "").strip().lower()
    defaults = PROFILES.get(profile, {})
    if defaults:
        with _LOAD_LOCK:
            seeded: list[str] = []
            for key, val in defaults.items():
                if os.environ.get(key) in (None, ""):
                    os.environ[key] = val
                    seeded.append(key)
            try:
                cfg = Config()
            finally:
                for key in seeded:
                    os.environ.pop(key, None)
    else:
        cfg = Config()
    cfg.profile_name = profile or "default"
    if cfg.fast:
        cfg.extract_mode = "classical"  # no LLM extraction or summaries
    return cfg
