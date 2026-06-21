"""Register the local stdio MCP server into **every** detected AI client (WP-25).

``mta setup`` extends ``mta setup-claude`` beyond Claude to all the MCP-capable
clients people actually use, each written *idempotently*, with a timestamped
backup, through the same crash-safe atomic writer (:func:`mta.core.setup._atomic_write_text`)
— so a single command makes the same local, token-free memory available to Claude,
Gemini, Cursor, VS Code, Windsurf, OpenAI Codex (ChatGPT's coding agent) and Grok.

Only **local stdio** is configured (the default ``mta serve``) — no network, no
token, nothing through the model, so every invariant holds. Clients that *only*
accept remote/HTTPS MCP (the ChatGPT app, the xAI API) can't be auto-registered to
a local process; ``mta recipes`` prints their manual HTTP/REST setup instead.

Design notes (verified against each vendor's current docs):
  * Most clients use top-level JSON ``mcpServers`` with ``{command, args, env}``.
  * **VS Code** is the exception — its ``mcp.json`` uses top-level ``servers`` and
    each stdio entry needs an explicit ``"type": "stdio"``.
  * **OpenAI Codex** stores config as **TOML** (``[mcp_servers."<name>"]``), so it
    gets an append-or-create writer that needs no third-party TOML *writer*
    dependency (keeping the dependency-free invariant).
  * **Grok Build** auto-discovers the repo's ``.mcp.json`` / a Claude config, so
    configuring Claude already reaches it; we surface that in the recipes.

Detection is side-effect-free (filesystem + ``PATH`` only): a client is "present"
if its config file exists, its config directory exists, or its CLI is on ``PATH``.
Absent clients are reported ``skipped`` and never written.
"""
from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .setup import (
    SERVER_NAME,
    _atomic_write_text,
    _backup_config,
    _merge_into,
    _mta_command,
    _roaming_appdata,
    claude_code_config_path,
    claude_desktop_config_path,
)


# ---------------------------------------------------------------------------
# Per-client config paths (cross-platform).
# ---------------------------------------------------------------------------

def _home() -> Path:
    return Path.home()


def gemini_config_path() -> Path:
    return _home() / ".gemini" / "settings.json"


def codex_config_path() -> Path:
    base = os.environ.get("CODEX_HOME")
    return (Path(base) if base else _home() / ".codex") / "config.toml"


def cursor_config_path() -> Path:
    return _home() / ".cursor" / "mcp.json"


def windsurf_config_path() -> Path:
    return _home() / ".codeium" / "windsurf" / "mcp_config.json"


def vscode_config_path() -> Path:
    """VS Code's per-user ``mcp.json`` (key ``servers``, not ``mcpServers``)."""
    home = _home()
    if sys.platform == "darwin":
        return home / "Library" / "Application Support" / "Code" / "User" / "mcp.json"
    if os.name == "nt":
        return _roaming_appdata(home) / "Code" / "User" / "mcp.json"
    return home / ".config" / "Code" / "User" / "mcp.json"


# ---------------------------------------------------------------------------
# Client registry.
# ---------------------------------------------------------------------------

@dataclass
class ClientSpec:
    id: str
    label: str
    path: Callable[[], Path]
    fmt: str = "json"                  # "json" | "toml"
    container_key: str = "mcpServers"  # JSON only
    stdio_type: bool = False           # VS Code wants {"type": "stdio", ...}
    bins: tuple[str, ...] = ()         # CLIs whose presence on PATH implies the client
    note: str = ""


CLIENTS: tuple[ClientSpec, ...] = (
    ClientSpec("claude_desktop", "Claude Desktop", claude_desktop_config_path,
               bins=()),
    ClientSpec("claude_code", "Claude Code", claude_code_config_path,
               bins=("claude",)),
    ClientSpec("gemini", "Gemini CLI", gemini_config_path,
               bins=("gemini",)),
    ClientSpec("codex", "OpenAI Codex (ChatGPT)", codex_config_path, fmt="toml",
               bins=("codex",)),
    ClientSpec("cursor", "Cursor", cursor_config_path,
               bins=("cursor",)),
    ClientSpec("vscode", "VS Code", vscode_config_path, container_key="servers",
               stdio_type=True, bins=("code", "code-insiders")),
    ClientSpec("windsurf", "Windsurf", windsurf_config_path,
               bins=("windsurf",)),
)

_BY_ID = {c.id: c for c in CLIENTS}


def _present(spec: ClientSpec) -> bool:
    """A client is installed if its config file exists, its *dedicated* config directory
    exists, or its CLI is on PATH. Pure detection — touches nothing.

    A config that lives directly in ``$HOME`` (e.g. Claude Code's ``~/.claude.json``)
    must not count its parent — home always exists — so it relies on the file or the CLI
    being present, never a bare-home false positive."""
    p = spec.path()
    if p.exists():
        return True
    parent = p.parent
    try:
        if parent.exists() and parent.resolve() != _home().resolve():
            return True
    except OSError:
        pass
    return any(shutil.which(b) for b in spec.bins)


def detect_clients() -> list[dict]:
    """Side-effect-free presence report for every known client."""
    out = []
    for spec in CLIENTS:
        out.append({"id": spec.id, "label": spec.label,
                    "path": str(spec.path()), "present": _present(spec)})
    return out


# ---------------------------------------------------------------------------
# Entry builders.
# ---------------------------------------------------------------------------

def _json_entry(spec: ClientSpec, command: list[str], env: dict | None) -> dict:
    entry: dict = {"command": command[0], "args": command[1:]}
    if spec.stdio_type:
        entry = {"type": "stdio", **entry}
    if env:
        entry["env"] = dict(env)
    return entry


def _toml_key(key: str) -> str:
    """A TOML bare key where possible, else a quoted key."""
    import re
    if re.fullmatch(r"[A-Za-z0-9_-]+", key):
        return key
    return _toml_str(key)


def _toml_str(value: str) -> str:
    """A TOML basic string. JSON string escaping is a safe superset for our values
    (ASCII paths / MTA_* env), and avoids a TOML *writer* dependency."""
    import json
    return json.dumps(str(value))


def _toml_block(name: str, command: list[str], env: dict | None) -> str:
    lines = [f'[mcp_servers.{_toml_str(name)}]',
             f"command = {_toml_str(command[0])}",
             "args = [" + ", ".join(_toml_str(a) for a in command[1:]) + "]"]
    if env:
        lines.append("")
        lines.append(f'[mcp_servers.{_toml_str(name)}.env]')
        for k, v in env.items():
            lines.append(f"{_toml_key(k)} = {_toml_str(v)}")
    return "\n".join(lines) + "\n"


def _toml_has_table(text: str, name: str) -> bool:
    """Cheap textual check for an existing ``[mcp_servers.<name>]`` table (used as a
    fallback when no TOML parser is importable on the 3.10 floor).

    Tolerant of the legal non-canonical spellings — intra-bracket/dot whitespace and a
    trailing ``#`` comment — and of all three key quotings (double / single / bare), so a
    hand-written table with our server name is detected and we never append a duplicate
    (which would make the file invalid TOML)."""
    import re
    n = re.escape(name)
    key = rf"(?:\"{n}\"|'{n}'|{n})"                                 # double / single / bare key
    pat = rf"(?m)^\s*\[\s*mcp_servers\s*\.\s*{key}\s*\]\s*(?:#.*)?$"
    return bool(re.search(pat, text))


def _merge_toml(spec: ClientSpec, command: list[str], env: dict | None, *,
                name: str = SERVER_NAME) -> dict:
    """Register the server in a Codex-style ``config.toml`` by **append-or-create** —
    we never re-emit the user's existing tables, so comments/formatting survive and no
    TOML writer dependency is needed. If our table is already present we report
    ``changed=False`` (an in-place value *update* would need ``tomlkit``; noted)."""
    path = spec.path()
    block = _toml_block(name, command, env)
    try:
        if path.exists():
            raw = path.read_text(encoding="utf-8")
            present = False
            try:  # prefer a real parser when one is importable
                import tomllib as _toml  # py3.11+
            except ModuleNotFoundError:
                try:
                    import tomli as _toml  # type: ignore  # backport on the 3.10 floor
                except ModuleNotFoundError:
                    _toml = None
            if _toml is not None:
                try:
                    data = _toml.loads(raw)
                    present = name in (data.get("mcp_servers") or {})
                except Exception:  # noqa: BLE001 - malformed TOML: fall back to text scan
                    present = _toml_has_table(raw, name)
            else:
                present = _toml_has_table(raw, name)
            if present:
                return {"path": str(path), "status": "ok", "changed": False, "backup": None,
                        "note": "already registered (in-place update needs a manual edit)"}
            backed_up = _backup_config(path)
            sep = "" if raw.endswith("\n") or not raw else "\n"
            _atomic_write_text(path, raw + sep + "\n" + block)
            return {"path": str(path), "status": "ok", "changed": True, "backup": str(backed_up)}
        _atomic_write_text(path, block)
        return {"path": str(path), "status": "ok", "changed": True, "backup": None}
    except OSError as exc:
        return {"path": str(path), "status": "error", "changed": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Orchestration.
# ---------------------------------------------------------------------------

def _configure_one(spec: ClientSpec, command: list[str], env: dict | None,
                   *, name: str = SERVER_NAME) -> dict:
    if spec.fmt == "toml":
        return _merge_toml(spec, command, env, name=name)
    return _merge_into(spec.path(), _json_entry(spec, command, env),
                       name=name, container_key=spec.container_key)


def setup_all(*, env: dict | None = None, only: list[str] | None = None,
              exclude: list[str] | None = None, write: bool = True,
              name: str = SERVER_NAME) -> dict:
    """Register the stdio server in every *detected* client (or just ``only``).

    ``write=False`` is a dry run: it reports what *would* change without touching any
    file. One client failing (e.g. its config is open/locked) never aborts the others.
    """
    from .platform import bootstrap_path
    bootstrap_path()  # GUI clients don't inherit the shell PATH; heal ours before resolving `mta`
    command = _mta_command()

    # ``None`` = no --only filter (configure all detected); a *given* but empty/whitespace
    # --only narrows to nothing rather than silently widening to everything.
    only_set = None if only is None else {s.strip() for s in only if s.strip()}
    excl_set = {s.strip() for s in (exclude or [])}

    results: dict = {"server": name, "command": command, "write": write, "targets": {}}
    for spec in CLIENTS:
        if only_set is not None and spec.id not in only_set:
            continue
        if spec.id in excl_set:
            continue
        if not _present(spec):
            results["targets"][spec.id] = {"path": str(spec.path()), "status": "skipped",
                                           "changed": False, "reason": "client not detected"}
            continue
        if not write:
            results["targets"][spec.id] = {"path": str(spec.path()), "status": "ok",
                                           "changed": None, "would_configure": True}
            continue
        r = _configure_one(spec, command, env, name=name)
        r["label"] = spec.label
        results["targets"][spec.id] = r
    return results


def render_summary(result: dict) -> str:
    """Human-readable rendering of :func:`setup_all`."""
    mode = "Would register" if result.get("write") is False else "Registered"
    lines = [f"{mode} MCP server '{result['server']}' → {' '.join(result['command'])}", ""]
    label = {c.id: c.label for c in CLIENTS}
    configured = 0
    for cid, r in result.get("targets", {}).items():
        name = r.get("label") or label.get(cid, cid)
        status = r.get("status")
        if status == "ok":
            if result.get("write") is False:
                tag = "would configure"
            elif r.get("changed"):
                tag = "added/updated"; configured += 1
            else:
                tag = "already up to date"; configured += 1
            line = f"  [ok]   {name}: {r['path']}  ({tag})"
            if r.get("note"):
                line += f"  — {r['note']}"
            lines.append(line)
            if r.get("backup"):
                lines.append(f"           backup: {r['backup']}")
        elif status == "skipped":
            lines.append(f"  [--]   {name}: not detected (skipped)")
        else:
            lines.append(f"  [!!]   {name}: {r['path']}  ({r.get('error')})")
    lines.append("")
    if result.get("write") is False:
        lines.append("Dry run — nothing was written. Re-run without --dry-run to apply.")
    else:
        lines.append(f"Configured {configured} client(s). Restart each client to load the server.")
        lines.append("ChatGPT app & the xAI API accept only remote MCP — see `mta recipes` "
                     "for their HTTP/REST setup. Grok Build auto-discovers the Claude config.")
    return "\n".join(lines)


__all__ = ["CLIENTS", "ClientSpec", "detect_clients", "setup_all", "render_summary"]
