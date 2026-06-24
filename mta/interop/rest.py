"""WP-22 — local REST gateway: the eleven tools over plain JSON HTTP.

Serves exactly the OpenAPI 3.1 surface that :mod:`mta.interop.schemas` describes —
``POST /tools/{name}`` with a JSON body of the tool's arguments returns the tool's
token-free result dict — for clients that speak REST but not MCP (curl, scripts,
OpenAPI-generated SDKs). Opt-in via ``mta serve --rest``; stdio (and the WP-20 MCP
HTTP transport) are unchanged.

Security reuses the WP-20 transport seam so there's one hardening story:

* **Loopback only by default** — binds ``127.0.0.1`` and refuses a non-loopback host
  unless ``--allow-remote`` (``MTA_HTTP_ALLOW_REMOTE=on``).
* **Mandatory bearer token** — the *same* token as the MCP HTTP transport
  (``transport.resolve_token`` → shared ``state/http_token``, ``0600``). Only the
  unauthenticated ``/healthz`` liveness probe is open; everything else needs the token.
* **Host-header allowlist** — a DNS-rebinding defense (the bound ``host:port`` + loopback
  aliases, extendable via ``MTA_HTTP_ALLOWED_HOSTS``), so a browser page can't drive it.

Invariants preserved: token-free (returns the same small tool dicts; nothing is sent
through the model), 100% local / no telemetry (no outbound calls), and **no new
top-level dependency** — ``starlette``/``uvicorn`` ship with ``mcp``. Blocking tool
calls run in a threadpool so a long digest never stalls the event loop; the store's
own cross-process locking keeps concurrent calls safe.
"""
from __future__ import annotations

import json
import sys

from ..core.config import Config, load as load_config
from ..transport import (
    HEALTH_PATH,
    BearerAuthMiddleware,
    is_loopback,
    resolve_token,
)
from .schemas import to_openapi

OPENAPI_PATH = "/openapi.json"


def _csv(value: str) -> list[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


def _tool_registry() -> dict:
    """Map tool name → the plain function defined in ``mta.server``.

    Imported lazily so this module stays import-light. Only these names are
    dispatchable — the route never calls an arbitrary attribute."""
    from .. import server

    fns = (
        server.digest, server.convert, server.recall, server.memory_overview,
        server.export_memory, server.list_digestible, server.forget,
        server.memory_status, server.diff_memory, server.import_memory,
        server.merge_memory,
    )
    return {fn.__name__: fn for fn in fns}


def _allowed_hosts(cfg: Config, host: str, port: int) -> set[str]:
    """Allowlisted ``Host`` values: the bound ``host:port`` (+ loopback aliases when
    local), plus any operator-supplied entries (reverse-proxy use)."""
    hosts = {f"{host}:{port}"}
    if is_loopback(host):
        for alias in ("127.0.0.1", "localhost", "[::1]"):
            hosts.add(f"{alias}:{port}")
    hosts.update(_csv(cfg.http_allowed_hosts))
    return hosts


class HostAllowlistMiddleware:
    """Pure-ASGI Host-header gate (DNS-rebinding defense).

    Rejects any HTTP request whose ``Host`` is not allowlisted with ``421 Misdirected
    Request`` (the same status the MCP SDK uses), before auth or routing run."""

    def __init__(self, app, allowed_hosts: set[str]):
        self.app = app
        self._hosts = {h.lower() for h in allowed_hosts}

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "http" and self._hosts:
            host = ""
            for key, value in scope.get("headers") or ():
                if key == b"host":
                    host = value.decode("latin-1").strip().lower()
                    break
            if host not in self._hosts:
                body = json.dumps(
                    {"status": "error", "error": "misdirected_request",
                     "detail": f"Host {host!r} is not allowed"}
                ).encode("utf-8")
                await send({"type": "http.response.start", "status": 421,
                            "headers": [(b"content-type", b"application/json"),
                                        (b"content-length", str(len(body)).encode())]})
                await send({"type": "http.response.body", "body": body})
                return
        await self.app(scope, receive, send)


def build_rest_app(cfg: Config, *, host: str, port: int, token: str):
    """Return the wrapped REST ASGI app: ``HostAllowlist(BearerAuth(routes))``."""
    from starlette.applications import Starlette
    from starlette.concurrency import run_in_threadpool
    from starlette.responses import JSONResponse
    from starlette.routing import Route

    tools = _tool_registry()
    openapi_doc = to_openapi()  # static surface description — build once (sync context)

    async def openapi(request):
        return JSONResponse(openapi_doc)

    async def call_tool(request):
        name = request.path_params["name"]
        fn = tools.get(name)
        if fn is None:
            return JSONResponse({"status": "error", "error": f"unknown tool {name!r}"},
                                status_code=404)
        raw = await request.body()
        try:
            body = json.loads(raw) if raw.strip() else {}
        except (json.JSONDecodeError, ValueError):
            return JSONResponse({"status": "error", "error": "request body must be JSON"},
                                status_code=400)
        if not isinstance(body, dict):
            return JSONResponse(
                {"status": "error", "error": "request body must be a JSON object of arguments"},
                status_code=400)
        try:
            # Tool calls can block (conversion, embeddings) — keep the loop responsive.
            result = await run_in_threadpool(lambda: fn(**body))
        except TypeError as exc:  # wrong/missing arguments for this tool
            return JSONResponse({"status": "error", "error": f"bad arguments for {name!r}: {exc}"},
                                status_code=400)
        return JSONResponse(result)

    # /healthz is served unauthenticated by BearerAuthMiddleware itself.
    routes = [
        Route(OPENAPI_PATH, openapi, methods=["GET"]),
        Route("/tools/{name}", call_tool, methods=["POST"]),
    ]
    app = Starlette(routes=routes)
    app = BearerAuthMiddleware(app, token, health_path=HEALTH_PATH)
    app = HostAllowlistMiddleware(app, _allowed_hosts(cfg, host, port))
    return app


def client_recipe(host: str, port: int, token: str) -> dict:
    """Connection recipe for REST clients (a curl example + the base URL)."""
    base = f"http://{host}:{port}"
    return {
        "surface": "rest",
        "base_url": base,
        "openapi": f"{base}{OPENAPI_PATH}",
        "health": f"{base}{HEALTH_PATH}",
        "headers": {"Authorization": f"Bearer {token}"},
        "curl_example": (
            f"curl -s {base}/tools/recall -H 'Authorization: Bearer {token}' "
            f"-H 'Content-Type: application/json' -d '{{\"query\":\"...\"}}'"
        ),
    }


def serve(cfg: Config | None = None, *, host: str | None = None, port: int | None = None,
          allow_remote: bool | None = None, banner: bool = True) -> None:
    """Run the REST gateway (blocks until stopped). Loopback-guarded; bearer-gated."""
    cfg = cfg or load_config()
    host = host or cfg.http_host
    port = int(port or cfg.http_port)
    allow_remote = cfg.http_allow_remote if allow_remote is None else allow_remote

    if not is_loopback(host) and not allow_remote:
        raise SystemExit(
            f"Refusing to bind the REST gateway to non-loopback host {host!r} without "
            "--allow-remote (or MTA_HTTP_ALLOW_REMOTE=on).\nBinding beyond 127.0.0.1 "
            "exposes your local memory to the network — put a TLS reverse proxy in front "
            "first; see SECURITY.md.")

    token, source = resolve_token(cfg)
    app = build_rest_app(cfg, host=host, port=port, token=token)
    if banner:
        _print_banner(host=host, port=port, token=token, token_source=source,
                      allow_remote=allow_remote)
    import uvicorn

    uvicorn.run(app, host=host, port=port, log_level="warning")


def _print_banner(*, host: str, port: int, token: str, token_source: str,
                  allow_remote: bool) -> None:
    r = client_recipe(host, port, token)
    lines = [
        "",
        "  Memorised them All — REST gateway (plain JSON over HTTP)",
        f"    Base:    {r['base_url']}",
        f"    Token:   {token}   ({token_source})",
        f"    OpenAPI: {r['openapi']}   (needs the bearer token)",
        f"    Health:  {r['health']}   (no auth; liveness only)",
        "",
        "  Example:",
        f"    {r['curl_example']}",
        "",
    ]
    if allow_remote and not is_loopback(host):
        lines += [
            "  ⚠ SECURITY: bound to a NON-loopback address. The bearer token is the only",
            "    guard over the network — terminate TLS at a reverse proxy and never expose",
            "    this on an untrusted network.",
            "",
        ]
    sys.stderr.write("\n".join(lines) + "\n")
    sys.stderr.flush()
