"""Memorised them All — MCP server (stdio) for Claude and every other MCP-capable client.

Claude Desktop / Claude Code launch it directly; ``mta setup`` also registers it with
Gemini CLI, Cursor, VS Code, Windsurf and OpenAI Codex (and Grok via config auto-discovery).
Exposes eleven token-free tools. Every tool returns only compact metadata or a
small, relevant slice of memory — never document contents — so digesting and
recalling whole folders costs ~0 context tokens. All work runs locally and
is fully deterministic + model-free: no LLM, no embedding model, no GPU, no network.
"""
from __future__ import annotations

import os
from pathlib import Path

from .core import recall as recall_mod
from .core import render, store, updater
from .core.config import load as load_config, persist_config
from .core.digest import digest as run_digest
from .core.platform import summary as platform_summary

try:
    from mcp.server.fastmcp import FastMCP
except Exception as exc:  # pragma: no cover - only when mcp not installed
    raise SystemExit("The 'mcp' package is required to run the server: pip install mcp") from exc


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

    Fully deterministic and model-free: extraction, summaries and embeddings all use
    the on-device classical/hash path, so two digests of the same corpus match."""
    if not isinstance(paths, list) or not paths or not all(
            isinstance(p, str) and p.strip() for p in paths):
        return _err("'paths' must be a non-empty list of file/dir/glob strings")
    cfg = _cfg(project)
    try:
        return run_digest(cfg, paths, reset=reset, fast=fast)
    except Exception as exc:  # noqa: BLE001 - never surface a raw traceback to the client
        return _err(f"digest failed: {exc}", type=type(exc).__name__)


def convert(paths: list[str], out_dir: str | None = None, project: str | None = None) -> dict:
    """Convert files/dirs/globs to Markdown locally and write the .md files to ``out_dir``
    (default: a ``markdown_converted/`` folder beside the input). Legacy Bengali
    (Bijoy/SutonnyMJ ANSI fonts) is auto-upgraded to Unicode during conversion.

    Token-free: returns ONLY counts + output paths, never document text. ``digest`` runs
    this same conversion first, so converting to Markdown is the default everywhere."""
    if not isinstance(paths, list) or not paths or not all(
            isinstance(p, str) and p.strip() for p in paths):
        return _err("'paths' must be a non-empty list of file/dir/glob strings")
    cfg = _cfg(project)
    try:
        from .core.digest import convert_to_markdown
        return convert_to_markdown(cfg, paths, out_dir=out_dir)
    except Exception as exc:  # noqa: BLE001 - never surface a raw traceback to the client
        return _err(f"convert failed: {exc}", type=type(exc).__name__)


def recall(query: str, project: str | None = None, k: int = 0,
           projects: list[str] | None = None, doc: str | None = None,
           entity_type: str | None = None) -> dict:
    """Answer from memory: returns a small, relevant slice (theme summaries +
    entity cards with provenance) — never whole documents.

    Optional filters (v3.1): ``doc`` limits hits to those citing one source document;
    ``entity_type`` limits to entity hits of a type (person/org/place/…). ``projects``
    federates the search across several named memories at once (each hit tagged with its
    project)."""
    if not isinstance(query, str) or not query.strip():
        return _err("'query' must be a non-empty string")
    if projects is not None and not (isinstance(projects, list)
                                     and all(isinstance(p, str) for p in projects)):
        return _err("'projects' must be a list of project-name strings")
    cfg = _cfg(project)
    try:
        return recall_mod.recall(cfg, query, k=k or None, projects=projects,
                                 doc=doc, entity_type=entity_type)
    except Exception as exc:  # noqa: BLE001
        return _err(f"recall failed: {exc}", type=type(exc).__name__)


def memory_overview(project: str | None = None) -> dict:
    """Return the compact synopsis, stats and theme list for a project's memory."""
    return recall_mod.overview(_cfg(project))


def export_memory(dest: str, project: str | None = None) -> dict:
    """Export the memory (memory.md, per-document notes, graph.json) as portable
    Markdown files to a destination directory."""
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


def forget(project: str | None = None, secure: bool = False) -> dict:
    """Delete a project's memory (knowledge graph, converted Markdown, summaries
    and notes). Irreversible. Pass the project name explicitly. ``secure=True``
    overwrites every file's bytes with random data before removal (best-effort — it
    cannot guarantee erasure on SSD/flash/copy-on-write/synced storage)."""
    return store.delete_project(_cfg(project), secure=bool(secure))


def diff_memory(other: str, project: str | None = None) -> dict:
    """Compare two project memories (read-only): documents added/removed/changed (matched by
    portable content hash), entities and themes only-in-each, and a stats delta. Token-free."""
    if not isinstance(other, str) or not other.strip():
        return _err("'other' must be a non-empty project name to compare against")
    cfg = _cfg(project)
    try:
        from .core import interchange
        return interchange.diff_memory(cfg, other, project=project)
    except Exception as exc:  # noqa: BLE001
        return _err(f"diff_memory failed: {exc}", type=type(exc).__name__)


def import_memory(src: str, project: str | None = None) -> dict:
    """Import a previously-exported bundle directory (graph.json + recall sidecars + notes)
    into a project, making it recall-ready on this machine. Backs up any existing store
    first. A recall-only snapshot — re-digesting the project replaces it. Token-free."""
    if not isinstance(src, str) or not src.strip():
        return _err("'src' must be a non-empty path to an exported bundle directory")
    cfg = _cfg(project)
    try:
        from .core import interchange
        return interchange.import_memory(cfg, src, project=project)
    except Exception as exc:  # noqa: BLE001
        return _err(f"import_memory failed: {exc}", type=type(exc).__name__)


def merge_memory(sources: list[str], into: str) -> dict:
    """Merge several source projects' converted corpora into a NEW project and rebuild one
    coherent memory (deterministic, model-free) — as if their files were digested together.
    Returns digest-style stats (token-free)."""
    if not isinstance(sources, list) or not sources or not all(
            isinstance(s, str) and s.strip() for s in sources):
        return _err("'sources' must be a non-empty list of project names")
    if not isinstance(into, str) or not into.strip():
        return _err("'into' must be a non-empty target project name")
    cfg = _cfg(into)
    try:
        from .core import interchange
        return interchange.merge_memory(cfg, sources, into)
    except Exception as exc:  # noqa: BLE001
        return _err(f"merge_memory failed: {exc}", type=type(exc).__name__)


def memory_status() -> dict:
    """Report the local stack: Tesseract, MarkItDown version, platform tuning,
    and existing projects. Fully deterministic + model-free (no inference engine)."""
    return _status()


def _status() -> dict:
    cfg = load_config()
    # v2 is fully model-free: there is no inference engine to probe. Memories always
    # build in the deterministic, on-device path.
    health = "Fully deterministic, model-free mode — no external AI engine is used."
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
        "backend": {"kind": "deterministic", "local": True, "model_free": True},
        "health": health,
        "tesseract": shutil.which("tesseract") is not None,
        "ffmpeg": shutil.which("ffmpeg") is not None,
        "markitdown_version": mid,
        "platform": platform_summary(),
        "auto_update": cfg.auto_update,
        "config_file": cfg_file,
        "dependencies": dep_summary,
        "projects": store.list_projects(cfg),
    }


def build_server() -> FastMCP:
    """Construct a fresh MCP server with all eleven tools registered.

    A factory (not just a module singleton) so each transport owns its server +
    session manager: the stdio launcher and an opt-in HTTP server (mta/transport.py)
    never share session state, and tests can build/tear down repeatedly. The
    module-level ``mcp`` below is the shared instance the stdio entrypoint
    (``python -m mta.server``) and tooling import."""
    srv = FastMCP("memorised-them-all")
    for fn in (digest, convert, recall, memory_overview, export_memory,
               list_digestible, forget, memory_status,
               diff_memory, import_memory, merge_memory):
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
