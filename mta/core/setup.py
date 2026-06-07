"""Register the MCP server in the host's Claude config (the "Claude Setup file").

``mta setup-claude`` — run automatically by ``install.sh`` and available by hand —
merges an ``mcpServers`` entry that points at this ``mta`` binary into Claude
Desktop's ``claude_desktop_config.json`` (and Claude Code's ``~/.claude.json`` when
present), **idempotently** and with a timestamped backup. So a fresh install is
usable without hand-editing JSON. The absolute ``mta`` path is used (GUI apps don't
inherit the shell ``PATH``).
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import time
from pathlib import Path

SERVER_NAME = "memorised-them-all"


def claude_desktop_config_path() -> Path:
    home = Path.home()
    if sys.platform == "darwin":
        return home / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", str(home)))
        return base / "Claude" / "claude_desktop_config.json"
    return home / ".config" / "Claude" / "claude_desktop_config.json"


def claude_code_config_path() -> Path:
    return Path.home() / ".claude.json"


def _mta_command() -> list[str]:
    """The command Claude should launch. Prefer the absolute ``mta`` on PATH (GUI apps
    don't inherit the shell PATH), else this interpreter running ``python -m mta.server``."""
    exe = shutil.which("mta")
    if exe:
        return [exe, "serve"]
    return [sys.executable, "-m", "mta.server"]


def _merge_into(path: Path, entry: dict, *, name: str = SERVER_NAME) -> dict:
    """Merge ``mcpServers[name] = entry`` into the JSON at ``path``, preserving every
    other key. Backs up an existing file first. Returns a small result dict."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        cfg: dict = {}
        backed_up = None
        if path.exists():
            backed_up = path.with_name(path.name + f".mta-backup-{int(time.time())}")
            shutil.copy2(path, backed_up)
            try:
                cfg = json.loads(path.read_text(encoding="utf-8") or "{}")
            except (json.JSONDecodeError, ValueError):
                cfg = {}
        if not isinstance(cfg, dict):
            cfg = {}
        # Coerce a non-dict ``mcpServers`` (e.g. a stray ``[]`` left by another tool)
        # to a dict, so the merge can neither silently no-op nor raise on ``.get``.
        servers = cfg.get("mcpServers")
        if not isinstance(servers, dict):
            servers = {}
            cfg["mcpServers"] = servers
        already = servers.get(name) == entry
        servers[name] = entry
        # Atomic write: stage to a UNIQUE temp file (mkstemp — so two concurrent
        # setup-claude runs, e.g. install.sh + a manual run, can't clobber a shared temp),
        # fsync, then ``os.replace`` (the single commit point) — a watcher like a running
        # Claude Desktop never sees a half-written file.
        import tempfile
        fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".mta-tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n")
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
        return {"path": str(path), "status": "ok",
                "changed": not already, "backup": str(backed_up) if backed_up else None}
    except OSError as exc:
        return {"path": str(path), "status": "error", "error": str(exc)}


def setup_claude(*, name: str = SERVER_NAME, env: dict | None = None,
                 include_code: bool = True) -> dict:
    """Register the MCP server in Claude Desktop (always) and Claude Code (if its
    config already exists). Idempotent; never clobbers other servers or keys."""
    entry: dict = {"command": _mta_command()[0], "args": _mta_command()[1:]}
    if env:
        entry["env"] = dict(env)

    results = {"server": name, "command": _mta_command(), "targets": {}}
    results["targets"]["claude_desktop"] = _merge_into(claude_desktop_config_path(), entry, name=name)
    code_path = claude_code_config_path()
    if include_code and code_path.exists():
        results["targets"]["claude_code"] = _merge_into(code_path, entry, name=name)
    return results


def render_summary(result: dict) -> str:
    lines = [f"Registered MCP server '{result['server']}' → {' '.join(result['command'])}", ""]
    for target, r in result.get("targets", {}).items():
        if r.get("status") == "ok":
            note = "added/updated" if r.get("changed") else "already up to date"
            lines.append(f"  ✓ {target}: {r['path']}  ({note})")
            if r.get("backup"):
                lines.append(f"      backup: {r['backup']}")
        else:
            lines.append(f"  ✗ {target}: {r['path']}  ({r.get('error')})")
    lines += ["", "Restart Claude (fully quit + reopen) to load the server."]
    return "\n".join(lines)
