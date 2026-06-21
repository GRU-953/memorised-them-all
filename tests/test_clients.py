"""WP-25 — multi-client MCP auto-configuration (`mta setup`).

Covers every client shape: JSON ``mcpServers`` (Claude/Gemini/Cursor/Windsurf), the
VS Code ``servers`` + ``type:stdio`` variant, and the Codex TOML append-or-create path.
Asserts idempotency, sibling-preservation, JSONC clobber-safety, detection gating, and
that nothing is written on a dry run. Fully offline.
"""
from __future__ import annotations

import json
import os

os.environ.setdefault("MTA_AUTO_UPDATE", "off")

import pytest

from mta.core import clients
from mta.core import setup as setupmod


# ---- JSON clients: merge, idempotency, sibling preservation -----------------

def test_json_merge_preserves_siblings_and_is_idempotent(tmp_path):
    cfg = tmp_path / "settings.json"
    cfg.write_text(json.dumps({"theme": "dark", "mcpServers": {"other": {"command": "x"}}}),
                   encoding="utf-8")
    spec = clients.ClientSpec("gemini", "Gemini", lambda: cfg)
    r1 = clients._configure_one(spec, ["mta", "serve"], None)
    assert r1["changed"] is True and r1["backup"]
    data = json.loads(cfg.read_text())
    assert data["theme"] == "dark"                                   # unrelated key kept
    assert data["mcpServers"]["other"] == {"command": "x"}           # other server kept
    assert data["mcpServers"]["memorised-them-all"] == {"command": "mta", "args": ["serve"]}
    r2 = clients._configure_one(spec, ["mta", "serve"], None)
    assert r2["changed"] is False and r2["backup"] is None           # idempotent, no new backup


def test_json_creates_when_absent_and_bakes_env(tmp_path):
    cfg = tmp_path / "nested" / "mcp.json"
    spec = clients.ClientSpec("cursor", "Cursor", lambda: cfg)
    clients._configure_one(spec, ["mta", "serve"], {"MTA_OCR_LANG": "eng+ben"})
    entry = json.loads(cfg.read_text())["mcpServers"]["memorised-them-all"]
    assert entry["command"] == "mta" and entry["env"]["MTA_OCR_LANG"] == "eng+ben"


def test_vscode_uses_servers_key_and_stdio_type(tmp_path):
    cfg = tmp_path / "mcp.json"
    spec = clients.ClientSpec("vscode", "VS Code", lambda: cfg,
                              container_key="servers", stdio_type=True)
    clients._configure_one(spec, ["mta", "serve"], None)
    data = json.loads(cfg.read_text())
    assert "mcpServers" not in data and "servers" in data            # VS Code variant
    entry = data["servers"]["memorised-them-all"]
    assert entry["type"] == "stdio" and entry["command"] == "mta"


def test_non_object_json_is_not_clobbered(tmp_path):
    # A valid JSON file whose top level is an array/scalar must be left intact, not
    # overwritten with just our server block.
    cfg = tmp_path / "mcp.json"
    cfg.write_text("[1, 2, 3]\n", encoding="utf-8")
    spec = clients.ClientSpec("cursor", "Cursor", lambda: cfg)
    r = clients._configure_one(spec, ["mta", "serve"], None)
    assert r["status"] == "error" and r["changed"] is False
    assert cfg.read_text() == "[1, 2, 3]\n"


def test_empty_json_file_is_created_normally(tmp_path):
    cfg = tmp_path / "mcp.json"
    cfg.write_text("   \n", encoding="utf-8")            # whitespace-only = fresh
    spec = clients.ClientSpec("cursor", "Cursor", lambda: cfg)
    r = clients._configure_one(spec, ["mta", "serve"], None)
    assert r["changed"] is True
    assert json.loads(cfg.read_text())["mcpServers"]["memorised-them-all"]["command"] == "mta"


def test_toml_detects_single_quoted_existing_table(tmp_path):
    cfg = tmp_path / "config.toml"
    cfg.write_text("[mcp_servers.'memorised-them-all']\ncommand = \"mta\"\n", encoding="utf-8")
    spec = clients.ClientSpec("codex", "Codex", lambda: cfg, fmt="toml")
    # Force the parserless text-scan path (the 3.10 floor) to exercise the literal-key match.
    import builtins
    real_import = builtins.__import__

    def _no_toml(name, *a, **k):
        if name in ("tomllib", "tomli"):
            raise ModuleNotFoundError(name)
        return real_import(name, *a, **k)

    builtins.__import__ = _no_toml
    try:
        r = clients._configure_one(spec, ["mta", "serve"], None)
    finally:
        builtins.__import__ = real_import
    assert r["changed"] is False                          # already present → no duplicate table


def test_toml_has_table_tolerates_noncanonical_headers():
    name = "memorised-them-all"
    for header in (
        '[mcp_servers."memorised-them-all"]',          # canonical (what we emit)
        "[mcp_servers.memorised-them-all]",            # bare key
        "[mcp_servers.'memorised-them-all']",          # single-quoted literal
        '[mcp_servers . "memorised-them-all"]',        # intra-bracket whitespace
        '[mcp_servers."memorised-them-all"]   # mine',  # trailing comment
    ):
        assert clients._toml_has_table(header + "\ncommand = \"x\"\n", name), header
    # a *different* server name must NOT match
    assert not clients._toml_has_table('[mcp_servers."other"]\n', name)


def test_setup_all_empty_only_configures_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(clients, "_mta_command", lambda: ["mta", "serve"])
    res = clients.setup_all(only=["", "  "])
    assert res["targets"] == {}                           # given-but-empty narrows to nothing


def test_jsonc_with_comments_is_not_clobbered(tmp_path):
    cfg = tmp_path / "mcp.json"
    original = '// my config\n{\n  "servers": {}\n}\n'
    cfg.write_text(original, encoding="utf-8")
    spec = clients.ClientSpec("vscode", "VS Code", lambda: cfg, container_key="servers")
    r = clients._configure_one(spec, ["mta", "serve"], None)
    assert r["status"] == "error" and r["changed"] is False
    assert cfg.read_text() == original                               # left byte-for-byte intact


# ---- Codex TOML: create, append, idempotent skip ----------------------------

def test_toml_creates_when_absent(tmp_path):
    cfg = tmp_path / "config.toml"
    spec = clients.ClientSpec("codex", "Codex", lambda: cfg, fmt="toml")
    r = clients._configure_one(spec, ["mta", "serve"], None)
    assert r["changed"] is True
    text = cfg.read_text()
    assert '[mcp_servers."memorised-them-all"]' in text
    assert 'command = "mta"' in text and 'args = ["serve"]' in text


def test_toml_appends_and_preserves_existing(tmp_path):
    cfg = tmp_path / "config.toml"
    cfg.write_text('model = "gpt-5"\n\n[mcp_servers."other"]\ncommand = "x"\n', encoding="utf-8")
    spec = clients.ClientSpec("codex", "Codex", lambda: cfg, fmt="toml")
    r = clients._configure_one(spec, ["mta", "serve"], None)
    assert r["changed"] is True and r["backup"]
    text = cfg.read_text()
    assert 'model = "gpt-5"' in text and '[mcp_servers."other"]' in text   # preserved
    assert '[mcp_servers."memorised-them-all"]' in text                    # appended
    # parseable & idempotent on a second run
    r2 = clients._configure_one(spec, ["mta", "serve"], None)
    assert r2["changed"] is False


def test_toml_round_trips_to_valid_toml(tmp_path):
    tomllib = pytest.importorskip("tomllib")
    cfg = tmp_path / "config.toml"
    spec = clients.ClientSpec("codex", "Codex", lambda: cfg, fmt="toml")
    clients._configure_one(spec, ["/abs/mta", "serve"], {"MTA_WORKERS": "0"})
    data = tomllib.loads(cfg.read_text())
    srv = data["mcp_servers"]["memorised-them-all"]
    assert srv["command"] == "/abs/mta" and srv["args"] == ["serve"]
    assert srv["env"]["MTA_WORKERS"] == "0"


# ---- detection + orchestration ----------------------------------------------

def test_detect_and_setup_skips_absent_clients(tmp_path, monkeypatch):
    # Point every client at a non-existent path under tmp and clear PATH detection.
    for spec in clients.CLIENTS:
        monkeypatch.setattr(spec, "path", lambda s=spec: tmp_path / "absent" / s.id / "c.json",
                            raising=False)
    monkeypatch.setattr(clients.shutil, "which", lambda *_a, **_k: None)
    monkeypatch.setattr(clients, "_mta_command", lambda: ["mta", "serve"])
    res = clients.setup_all()
    assert res["targets"] and all(t["status"] == "skipped" for t in res["targets"].values())


def test_only_filter_and_dry_run(tmp_path, monkeypatch):
    cfg = tmp_path / ".cursor" / "mcp.json"
    cfg.parent.mkdir(parents=True)                                   # make Cursor "present"
    monkeypatch.setattr(clients, "cursor_config_path", lambda: cfg)
    monkeypatch.setattr(clients._BY_ID["cursor"], "path", lambda: cfg, raising=False)
    monkeypatch.setattr(clients, "_mta_command", lambda: ["mta", "serve"])
    res = clients.setup_all(only=["cursor"], write=False)
    assert set(res["targets"]) == {"cursor"}
    assert res["targets"]["cursor"]["would_configure"] is True
    assert not cfg.exists()                                          # dry run wrote nothing


def test_cli_setup_dry_run_json(tmp_path, monkeypatch, capsys):
    from mta.cli import main
    monkeypatch.setattr(clients.shutil, "which", lambda *_a, **_k: None)
    for spec in clients.CLIENTS:
        monkeypatch.setattr(spec, "path", lambda s=spec: tmp_path / s.id / "c.json", raising=False)
    rc = main(["setup", "--dry-run", "--json"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["write"] is False and "targets" in out


# ---- setup_claude still behaves exactly as before ---------------------------

def test_windows_appdata_fallback(tmp_path, monkeypatch):
    # %APPDATA% unset on Windows must resolve to ~/AppData/Roaming, NOT bare ~ (which no
    # client reads). Test the helper directly (monkeypatching os.name on POSIX breaks
    # pathlib's WindowsPath construction, so we exercise the fallback logic itself).
    from mta.core.setup import _roaming_appdata
    monkeypatch.delenv("APPDATA", raising=False)
    assert _roaming_appdata(tmp_path) == tmp_path / "AppData" / "Roaming"   # unset → Roaming, not ~
    monkeypatch.setenv("APPDATA", str(tmp_path / "custom_roaming"))
    assert _roaming_appdata(tmp_path) == tmp_path / "custom_roaming"        # honours the env when set


def test_backup_is_chmod_0600(tmp_path):
    import os as _os, stat as _stat
    if _os.name == "nt":
        import pytest
        pytest.skip("POSIX permission semantics")
    cfg = tmp_path / "settings.json"
    cfg.write_text('{"mcpServers": {}}', encoding="utf-8")
    cfg.chmod(0o644)
    spec = clients.ClientSpec("gemini", "Gemini", lambda: cfg)
    r = clients._configure_one(spec, ["mta", "serve"], None)
    backup = r["backup"]
    assert backup and (_stat.S_IMODE(_os.stat(backup).st_mode) == 0o600)   # secrets not world-readable


def test_setup_claude_unchanged(tmp_path, monkeypatch):
    desktop = tmp_path / "claude_desktop_config.json"
    desktop.write_text(json.dumps({"preferences": {"x": 1}}), encoding="utf-8")
    monkeypatch.setattr(setupmod, "claude_desktop_config_path", lambda: desktop)
    monkeypatch.setattr(setupmod, "claude_code_config_path", lambda: tmp_path / "absent.json")
    monkeypatch.setattr(setupmod, "_mta_command", lambda: ["mta", "serve"])
    res = setupmod.setup_claude()
    d = json.loads(desktop.read_text())
    assert d["preferences"] == {"x": 1}
    assert d["mcpServers"]["memorised-them-all"] == {"command": "mta", "args": ["serve"]}
    assert res["targets"]["claude_desktop"]["changed"] is True
