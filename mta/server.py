"""Memorised them All — MCP server (stdio) for Claude Desktop & Claude Code.

Exposes eight token-free tools. Every tool returns only compact metadata or a
small, relevant slice of memory — never document contents — so digesting and
recalling whole folders costs ~0 Claude context tokens. All heavy work runs
locally; the local model server (Ollama) is started on demand and stopped after
``MTA_IDLE`` seconds of inactivity (default 5 minutes).
"""
from __future__ import annotations

import os
from pathlib import Path

from .core import recall as recall_mod
from .core import render, store, updater
from .core.config import load as load_config, persist_config
from .core.digest import digest as run_digest
from .core.lifecycle import OllamaManager
from .core.platform import summary as platform_summary

try:
    from mcp.server.fastmcp import FastMCP
except Exception as exc:  # pragma: no cover - only when mcp not installed
    raise SystemExit("The 'mcp' package is required to run the server: pip install mcp") from exc

# One Ollama manager per process so the idle watchdog and "started-by-us" flag
# are shared across all tool calls.
_OLLAMA: OllamaManager | None = None


def _ollama() -> OllamaManager:
    global _OLLAMA
    if _OLLAMA is None:
        _OLLAMA = OllamaManager(load_config())
    return _OLLAMA


def _cfg(project: str | None = None):
    cfg = load_config().with_project(project)
    # Kick a throttled, non-blocking auto-update on first activity.
    updater.start_background(cfg)
    return cfg


def _err(msg: str, **extra) -> dict:
    """Structured tool error — a bad call returns a small dict instead of crossing
    the MCP boundary as a raw traceback (still token-free)."""
    return {"status": "error", "error": msg, **extra}


def digest(paths: list[str], project: str | None = None, reset: bool = False,
           fast: bool = False) -> dict:
    """Convert files/dirs/globs to Markdown locally, then build a knowledge graph
    + layered memory. Returns ONLY counts, paths and graph stats (token-free).

    fast=True skips the local LLM (classical extraction + deterministic summaries,
    fully reproducible); the default uses the local LLM for higher accuracy."""
    if not isinstance(paths, list) or not paths or not all(
            isinstance(p, str) and p.strip() for p in paths):
        return _err("'paths' must be a non-empty list of file/dir/glob strings")
    cfg = _cfg(project)
    try:
        return run_digest(cfg, paths, reset=reset, fast=fast, ollama=_ollama())
    except Exception as exc:  # noqa: BLE001 - never surface a raw traceback to the client
        return _err(f"digest failed: {exc}", type=type(exc).__name__)


def recall(query: str, project: str | None = None, k: int = 0) -> dict:
    """Answer from memory: returns a small, relevant slice (theme summaries +
    entity cards with provenance) — never whole documents."""
    if not isinstance(query, str) or not query.strip():
        return _err("'query' must be a non-empty string")
    cfg = _cfg(project)
    try:
        return recall_mod.recall(cfg, query, k=k or None, ollama=_ollama())
    except Exception as exc:  # noqa: BLE001
        return _err(f"recall failed: {exc}", type=type(exc).__name__)


def memory_overview(project: str | None = None) -> dict:
    """Return the compact synopsis, stats and theme list for a project's memory."""
    return recall_mod.overview(_cfg(project))


def export_memory(dest: str, project: str | None = None) -> dict:
    """Export the memory (memory.md, per-document notes, graph.json, mind map) as
    portable Markdown files to a destination directory."""
    if not isinstance(dest, str) or not dest.strip():
        return _err("'dest' must be a non-empty destination directory path")
    return render.export_bundle(_cfg(project), dest)


def list_digestible(directory: str) -> dict:
    """List convertible files under a directory (paths + sizes only)."""
    if not isinstance(directory, str) or not directory.strip():
        return _err("'directory' must be a non-empty path")
    from .core.convert import SUPPORTED_EXTS
    base = Path(directory).expanduser()
    if not base.exists():
        return {"status": "not_found", "directory": str(base)}
    try:
        files = [p for p in base.rglob("*") if p.is_file()
                 and p.suffix.lower() in SUPPORTED_EXTS]
        out = []
        for p in files[:500]:
            try:
                out.append({"path": str(p), "bytes": p.stat().st_size})
            except OSError:
                continue  # file vanished/inaccessible between rglob and stat (TOCTOU)
        return {"status": "ok", "directory": str(base), "count": len(files), "files": out}
    except OSError as exc:  # noqa: BLE001
        return _err(f"could not list {base}: {exc}")


def forget(project: str | None = None) -> dict:
    """Delete a project's memory (graph, converted Markdown, vectors, mind map).
    Irreversible. Pass the project name explicitly."""
    return store.delete_project(_cfg(project))


def memory_status() -> dict:
    """Report the local stack: Ollama, models, Tesseract, MarkItDown version,
    platform tuning, and existing projects."""
    return _status()


def open_mindmap(project: str | None = None) -> dict:
    """Return the path to the offline interactive mind map for a project."""
    cfg = _cfg(project)
    if not cfg.mindmap_html.exists():
        return {"status": "no_memory", "project": cfg.project}
    return {"status": "ok", "project": cfg.project, "path": str(cfg.mindmap_html),
            "open_with": f"open '{cfg.mindmap_html}'"}


def _status() -> dict:
    cfg = load_config()
    o = _ollama()
    ollama_up = o.is_up()
    models = []
    if ollama_up:
        import json
        import urllib.request
        try:
            with urllib.request.urlopen(f"{o.host}/api/tags", timeout=3) as r:
                models = [m["name"] for m in json.loads(r.read()).get("models", [])]
        except Exception:  # noqa: BLE001
            pass
    try:
        import importlib.metadata as md
        mid = md.version("markitdown")
    except Exception:  # noqa: BLE001
        mid = None
    import shutil
    try:
        cfg_file = str(persist_config(cfg))  # snapshot the resolved config (R2)
    except OSError:
        cfg_file = None
    try:
        from .core import deps
        dep_summary = deps.scan(cfg, probe_bin_versions=False)["summary"]
    except Exception:  # noqa: BLE001
        dep_summary = None
    return {
        "status": "ok",
        "ollama_running": ollama_up,
        "ollama_models": models,
        "tesseract": shutil.which("tesseract") is not None,
        "ffmpeg": shutil.which("ffmpeg") is not None,
        "markitdown_version": mid,
        "platform": platform_summary(),
        "profile": cfg.profile_name,
        "auto_update": cfg.auto_update,
        "idle_seconds": cfg.idle_seconds,
        "config_file": cfg_file,
        "dependencies": dep_summary,
        "projects": store.list_projects(cfg),
    }


def build_server() -> FastMCP:
    """Construct a fresh MCP server with all eight tools registered.

    A factory (not just a module singleton) so each transport owns its server +
    session manager: the stdio launcher and an opt-in HTTP server (mta/transport.py)
    never share session state, and tests can build/tear down repeatedly. The
    module-level ``mcp`` below is the shared instance the stdio entrypoint
    (``python -m mta.server``) and tooling import."""
    srv = FastMCP("memorised-them-all")
    for fn in (digest, recall, memory_overview, export_memory,
               list_digestible, forget, memory_status, open_mindmap):
        srv.tool()(fn)
    return srv


mcp = build_server()


def main() -> None:
    """stdio entrypoint (unchanged default). HTTP is opt-in via ``mta serve --http``."""
    from .core.platform import bootstrap_path
    bootstrap_path()
    mcp.run()


if __name__ == "__main__":
    main()
