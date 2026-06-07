"""WP-20 — secure Streamable HTTP transport.

In-process ASGI tests (no real socket → robust on Linux/macOS/Windows CI). They
prove the security contract and a real MCP conformance handshake:

* bearer-token gate — 401 with no/invalid token, pass-through with a valid one;
* an unauthenticated liveness probe that never leaks the token;
* an authenticated initialize → initialized → tools/list that returns all 8 tools;
* DNS-rebinding rejection (a foreign Host header is refused even with a good token);
* token generation / 0600 persistence / reuse / env override;
* loopback-by-default and the non-loopback bind guard.

Everything here runs fully offline (no Ollama, no converters, no network egress);
``starlette`` + ``httpx`` arrive transitively with ``mcp``.
"""
from __future__ import annotations

import json
import os
import stat

import pytest

pytest.importorskip("starlette")
from starlette.testclient import TestClient  # noqa: E402

from mta import transport  # noqa: E402
from mta.core.config import Config  # noqa: E402

HOST, PORT, PATH = "127.0.0.1", 8765, "/mcp"
BASE_URL = f"http://{HOST}:{PORT}"
JSON_SSE = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
INIT = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                   "clientInfo": {"name": "pytest", "version": "0"}}}


def _cfg(tmp_path, *, token="") -> Config:
    """A Config rooted at a tmp HOME with deterministic HTTP knobs (independent of
    the ambient MTA_* environment)."""
    cfg = Config(home=tmp_path)
    cfg.http_token = token
    cfg.http_allow_remote = False
    cfg.http_allowed_hosts = ""
    cfg.http_allowed_origins = ""
    return cfg


def _app(cfg, token):
    return transport.build_app(cfg, host=HOST, port=PORT, path=PATH, token=token)


def _sse_json(text: str):
    for line in text.splitlines():
        if line.startswith("data:"):
            return json.loads(line[5:].strip())
    return None


# ---- token management -------------------------------------------------------

def test_token_generated_and_persisted_0600(tmp_path):
    cfg = _cfg(tmp_path)
    token, source = transport.resolve_token(cfg)
    assert source == "generated" and len(token) >= 32
    f = cfg.http_token_file
    assert f.exists() and f.read_text().strip() == token
    if os.name != "nt":  # Windows perms aren't POSIX bits
        assert stat.S_IMODE(f.stat().st_mode) == 0o600
    # a second resolve reuses the persisted token (stable across restarts)
    again, source2 = transport.resolve_token(_cfg(tmp_path))
    assert again == token and source2 == "persisted"


def test_token_env_override_not_persisted(tmp_path):
    cfg = _cfg(tmp_path, token="explicit-token-xyz")
    token, source = transport.resolve_token(cfg)
    assert token == "explicit-token-xyz" and source == "env"
    assert not cfg.http_token_file.exists()  # explicit token is never written out


# ---- auth gate --------------------------------------------------------------

def test_unauthenticated_request_rejected(tmp_path):
    cfg = _cfg(tmp_path)
    token, _ = transport.resolve_token(cfg)
    with TestClient(_app(cfg, token), base_url=BASE_URL) as c:
        r = c.post(PATH, json=INIT, headers=JSON_SSE)  # no Authorization
    assert r.status_code == 401
    assert r.json()["error"] == "unauthorized"
    assert "www-authenticate" in {k.lower() for k in r.headers}


def test_wrong_token_rejected(tmp_path):
    cfg = _cfg(tmp_path)
    token, _ = transport.resolve_token(cfg)
    headers = {**JSON_SSE, "Authorization": "Bearer not-the-token"}
    with TestClient(_app(cfg, token), base_url=BASE_URL) as c:
        r = c.post(PATH, json=INIT, headers=headers)
    assert r.status_code == 401


def test_health_probe_is_unauthenticated_and_leaks_no_secret(tmp_path):
    cfg = _cfg(tmp_path)
    token, _ = transport.resolve_token(cfg)
    with TestClient(_app(cfg, token), base_url=BASE_URL) as c:
        r = c.get(transport.HEALTH_PATH)  # no Authorization header
    assert r.status_code == 200 and r.json()["status"] == "ok"
    assert token not in r.text  # the liveness probe must never expose the token


# ---- conformance: a real authenticated MCP handshake ------------------------

def test_authenticated_handshake_lists_all_eight_tools(tmp_path):
    cfg = _cfg(tmp_path)
    token, _ = transport.resolve_token(cfg)
    headers = {**JSON_SSE, "Authorization": f"Bearer {token}"}
    with TestClient(_app(cfg, token), base_url=BASE_URL) as c:
        r = c.post(PATH, json=INIT, headers=headers)
        assert r.status_code == 200
        sid = r.headers.get("mcp-session-id")
        assert sid
        session = {**headers, "mcp-session-id": sid}
        n = c.post(PATH, json={"jsonrpc": "2.0", "method": "notifications/initialized"},
                   headers=session)
        assert n.status_code == 202
        tl = c.post(PATH, json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
                    headers=session)
        assert tl.status_code == 200
    tools = sorted(t["name"] for t in _sse_json(tl.text)["result"]["tools"])
    assert tools == ["convert", "digest", "export_memory", "forget", "list_digestible",
                     "memory_overview", "memory_status", "open_mindmap", "recall"]


# ---- DNS-rebinding protection ----------------------------------------------

def test_foreign_host_header_blocked_even_with_token(tmp_path):
    cfg = _cfg(tmp_path)
    token, _ = transport.resolve_token(cfg)
    headers = {**JSON_SSE, "Authorization": f"Bearer {token}", "Host": "evil.example.com"}
    with TestClient(_app(cfg, token), base_url=BASE_URL) as c:
        r = c.post(PATH, json=INIT, headers=headers)
    assert r.status_code >= 400  # SDK returns 421 for a disallowed Host


def test_security_settings_allowlist(tmp_path):
    cfg = _cfg(tmp_path)
    cfg.http_allowed_hosts = "proxy.example.com:*"
    settings = transport._security_settings(cfg, HOST, PORT)
    assert settings.enable_dns_rebinding_protection is True
    assert f"{HOST}:{PORT}" in settings.allowed_hosts
    assert "localhost:8765" in settings.allowed_hosts
    assert "proxy.example.com:*" in settings.allowed_hosts  # operator extension preserved


# ---- bind policy ------------------------------------------------------------

def test_loopback_default():
    assert Config().http_host == "127.0.0.1"
    assert transport.is_loopback("127.0.0.1")
    assert transport.is_loopback("localhost")
    assert transport.is_loopback("::1")
    assert not transport.is_loopback("0.0.0.0")
    assert not transport.is_loopback("192.168.1.10")


def test_remote_bind_refused_without_allow_remote(tmp_path):
    cfg = _cfg(tmp_path)
    with pytest.raises(SystemExit):
        transport.serve(cfg, transport="http", host="0.0.0.0",
                        allow_remote=False, banner=False)


def test_serve_http_loopback_invokes_uvicorn(tmp_path, monkeypatch, capsys):
    import uvicorn
    captured = {}
    monkeypatch.setattr(uvicorn, "run", lambda app, **kw: captured.update(kw, app=app))
    transport.serve(_cfg(tmp_path), transport="http", host=HOST, port=PORT, path=PATH, banner=True)
    assert captured["host"] == HOST and captured["port"] == PORT
    err = capsys.readouterr().err
    assert "Streamable HTTP" in err and "claude mcp add" in err


def test_serve_stdio_delegates_to_server_main(monkeypatch):
    import mta.server as srv
    called = {}
    monkeypatch.setattr(srv, "main", lambda: called.setdefault("stdio", True))
    transport.serve(transport="stdio")
    assert called.get("stdio") is True


def test_unknown_transport_rejected(tmp_path):
    with pytest.raises(ValueError):
        transport.serve(_cfg(tmp_path), transport="carrier-pigeon")


# ---- client recipe (the WP-24 seam) ----------------------------------------

def test_client_config_shape():
    cc = transport.client_config(HOST, PORT, PATH, "TOK")
    assert cc["url"] == f"{BASE_URL}{PATH}"
    assert cc["headers"]["Authorization"] == "Bearer TOK"
    assert cc["transport"] == "streamable-http"
    assert "claude mcp add --transport http" in cc["claude_code_add"]
    assert cc["mcp_json"]["memorised-them-all"]["url"] == f"{BASE_URL}{PATH}"
