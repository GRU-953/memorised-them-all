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


def _atomic_write_text(path: Path, text: str) -> None:
    """Crash-safe write: stage to a UNIQUE temp file (``mkstemp`` — so two concurrent
    runs, e.g. ``install.sh`` + a manual run, can't clobber a shared temp), ``fsync``,
    then ``os.replace`` (the single commit point) — a watcher (a running Claude Desktop,
    Cursor, …) never sees a half-written file. The temp lands in the target's own
    directory so the rename is same-filesystem (never a cross-device ``OSError``)."""
    import tempfile
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".mta-tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _merge_into(path: Path, entry: dict, *, name: str = SERVER_NAME,
                container_key: str = "mcpServers") -> dict:
    """Merge ``<container_key>[name] = entry`` into the JSON at ``path``, preserving every
    other key. Backs up an existing file **only when the content will change**. Returns a
    small result dict.

    Safety: a non-empty file that does not parse as JSON (e.g. JSONC with comments, which
    several MCP clients allow) is **left untouched** with ``status="error"`` rather than
    silently reset to ``{}`` — clobbering a user's whole config is worse than skipping.
    """
    try:
        cfg: dict = {}
        existed = path.exists()
        if existed:
            raw = path.read_text(encoding="utf-8")
            if raw.strip():
                try:
                    cfg = json.loads(raw)
                except (json.JSONDecodeError, ValueError):
                    return {"path": str(path), "status": "error", "changed": False,
                            "error": "existing config is not valid JSON (comments?); left untouched"}
        # A valid JSON document whose top level is not an object (e.g. ``[1,2,3]``) is
        # left untouched too — overwriting it would discard the user's data. (A fresh /
        # empty file keeps the ``{}`` default and is created normally.)
        if not isinstance(cfg, dict):
            return {"path": str(path), "status": "error", "changed": False,
                    "error": "existing config top-level is not a JSON object; left untouched"}
        # Coerce a non-dict container (e.g. a stray ``[]`` left by another tool) to a dict,
        # so the merge can neither silently no-op nor raise on ``.get``.
        servers = cfg.get(container_key)
        if not isinstance(servers, dict):
            servers = {}
            cfg[container_key] = servers
        already = existed and servers.get(name) == entry
        if already:
            return {"path": str(path), "status": "ok", "changed": False, "backup": None}
        servers[name] = entry
        backed_up = None
        if existed:
            backed_up = path.with_name(path.name + f".mta-backup-{int(time.time())}")
            shutil.copy2(path, backed_up)
        _atomic_write_text(path, json.dumps(cfg, indent=2, ensure_ascii=False) + "\n")
        return {"path": str(path), "status": "ok",
                "changed": True, "backup": str(backed_up) if backed_up else None}
    except OSError as exc:
        return {"path": str(path), "status": "error", "changed": False, "error": str(exc)}


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
