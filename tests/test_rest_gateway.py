"""WP-22 — local REST gateway (plain JSON over HTTP).

In-process ASGI tests (no real socket → robust on Linux/macOS/Windows CI). They
prove the security contract (loopback default, mandatory bearer, Host allowlist)
and that the eight tools are callable as `POST /tools/{name}` returning their
token-free dicts. Fully offline: `MTA_HOME` is redirected to a tmp dir and Ollama
is disabled, so no real memory is touched and nothing hits the network.
"""
from __future__ import annotations

import os

os.environ.setdefault("MTA_NO_OLLAMA", "1")
os.environ.setdefault("MTA_AUTO_UPDATE", "off")

import pytest

pytest.importorskip("starlette")
from starlette.testclient import TestClient  # noqa: E402

from mta.core.config import Config  # noqa: E402
from mta.interop import rest  # noqa: E402

HOST, PORT = "127.0.0.1", 8765
BASE_URL = f"http://{HOST}:{PORT}"
TOKEN = "rest-test-token-xyz"


def _auth(token=TOKEN):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def client(tmp_path, monkeypatch):
    """A TestClient over the REST app, with MTA_HOME isolated to a tmp dir."""
    monkeypatch.setenv("MTA_HOME", str(tmp_path))
    monkeypatch.setenv("MTA_NO_OLLAMA", "1")
    monkeypatch.setenv("MTA_AUTO_UPDATE", "off")
    cfg = Config(home=tmp_path)
    app = rest.build_rest_app(cfg, host=HOST, port=PORT, token=TOKEN)
    with TestClient(app, base_url=BASE_URL) as c:
        yield c


# ---- auth + health ----------------------------------------------------------

def test_health_is_unauthenticated(client):
    # /healthz is the only open route; served by the shared bearer-auth gate.
    r = client.get(rest.HEALTH_PATH)
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_tools_require_bearer(client):
    assert client.post("/tools/memory_status").status_code == 401


def test_wrong_token_rejected(client):
    r = client.post("/tools/memory_status", headers=_auth("nope"))
    assert r.status_code == 401


def test_openapi_behind_auth_then_served(client):
    assert client.get(rest.OPENAPI_PATH).status_code == 401      # no token
    r = client.get(rest.OPENAPI_PATH, headers=_auth())
    assert r.status_code == 200
    doc = r.json()
    assert doc["openapi"] == "3.1.0"
    assert "/tools/digest" in doc["paths"]                        # self-describes the surface


# ---- tool dispatch ----------------------------------------------------------

def test_memory_status_offline_ok(client):
    r = client.post("/tools/memory_status", headers=_auth())
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["ollama_running"] is False                        # offline, no network


def test_list_digestible(client, tmp_path):
    r = client.post("/tools/list_digestible", headers=_auth(),
                    json={"directory": str(tmp_path)})
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_recall_on_fresh_memory(client):
    r = client.post("/tools/recall", headers=_auth(), json={"query": "anything"})
    assert r.status_code == 200
    assert r.json()["status"] in ("no_memory", "ok", "low_confidence")


def test_unknown_tool_is_404(client):
    r = client.post("/tools/does_not_exist", headers=_auth(), json={})
    assert r.status_code == 404
    assert r.json()["status"] == "error"


def test_missing_required_arg_is_400(client):
    # digest requires `paths`
    r = client.post("/tools/digest", headers=_auth(), json={})
    assert r.status_code == 400
    assert "bad arguments" in r.json()["error"]


def test_unexpected_arg_is_400(client):
    r = client.post("/tools/memory_status", headers=_auth(), json={"bogus": 1})
    assert r.status_code == 400


def test_malformed_json_body_is_400(client):
    r = client.post("/tools/recall", headers=_auth(), content="{not valid json")
    assert r.status_code == 400


def test_non_object_body_is_400(client):
    r = client.post("/tools/recall", headers=_auth(), json=[1, 2, 3])
    assert r.status_code == 400


# ---- DNS-rebinding (Host allowlist) ----------------------------------------

def test_foreign_host_header_blocked(client):
    r = client.post("/tools/memory_status",
                    headers={**_auth(), "Host": "evil.example.com"})
    assert r.status_code == 421


def test_allowed_hosts_include_loopback_aliases(tmp_path):
    hosts = rest._allowed_hosts(Config(home=tmp_path), HOST, PORT)
    assert {"127.0.0.1:8765", "localhost:8765", "[::1]:8765"} <= hosts


# ---- bind policy + serve ----------------------------------------------------

def test_remote_bind_refused_without_allow_remote(tmp_path):
    with pytest.raises(SystemExit):
        rest.serve(Config(home=tmp_path), host="0.0.0.0", allow_remote=False, banner=False)


def test_serve_loopback_runs_uvicorn_and_persists_shared_token(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("MTA_HOME", str(tmp_path))
    import uvicorn
    captured = {}
    monkeypatch.setattr(uvicorn, "run", lambda app, **kw: captured.update(kw, app=app))
    rest.serve(Config(home=tmp_path), host=HOST, port=PORT, banner=True)
    assert captured["host"] == HOST and captured["port"] == PORT
    err = capsys.readouterr().err
    assert "REST gateway" in err and "curl" in err
    # the bearer token is the SAME file the MCP HTTP transport uses
    assert (tmp_path / "state" / "http_token").exists()


def test_client_recipe_shape():
    r = rest.client_recipe(HOST, PORT, "TOK")
    assert r["base_url"] == BASE_URL
    assert r["headers"]["Authorization"] == "Bearer TOK"
    assert "/tools/recall" in r["curl_example"]
