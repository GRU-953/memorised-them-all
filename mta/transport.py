"""Transport seam — stdio (default) and an opt-in, secure Streamable HTTP server.

``mta/server.py`` *defines* the eleven token-free tools; this module owns *how*
they are exposed. stdio stays the default (Claude Desktop / Claude Code launch
``python -m mta.server`` → stdio, unchanged). The HTTP transport is opt-in
(``mta serve --http``) and secure by construction:

* **Loopback only by default** — binds ``127.0.0.1`` unless ``--allow-remote``
  (``MTA_HTTP_ALLOW_REMOTE=on``) is given explicitly, with a printed warning.
* **Always authenticated** — every request must carry ``Authorization: Bearer
  <token>``. The token comes from ``MTA_HTTP_TOKEN`` or is auto-generated and
  persisted ``0600`` under ``state/``. There is no unauthenticated mode.
* **DNS-rebinding protection** — the SDK's Host/Origin allowlist stays on, so a
  web page cannot drive the local server through the user's browser.

This preserves every invariant: token-free (tool results are unchanged tiny
dicts), 100% local / no telemetry (no outbound calls; the token is only ever
written to a local 0600 file and echoed to stderr), and it adds **no** new
top-level dependency — ``starlette``/``uvicorn`` already ship with ``mcp``.
``client_config()`` is the seam WP-21/22/24 render their per-client recipes on.
"""
from __future__ import annotations

import json
import os
import secrets
import stat
import sys
import tempfile
from pathlib import Path

from .core.config import Config, load as load_config

DEFAULT_PORT = 8765
HEALTH_PATH = "/healthz"
_LOOPBACK = {"127.0.0.1", "::1", "localhost"}


def is_loopback(host: str) -> bool:
    """True for addresses that are only reachable from this machine."""
    h = (host or "").strip().lower().strip("[]")
    return h in _LOOPBACK or h.startswith("127.")


def _csv(value: str) -> list[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


# ---- bearer token ----------------------------------------------------------

def resolve_token(cfg: Config) -> tuple[str, str]:
    """Return ``(token, source)`` where ``source`` is ``env`` | ``persisted`` |
    ``generated``.

    Precedence: an explicit ``MTA_HTTP_TOKEN`` wins; otherwise a previously
    persisted token is reused; otherwise a fresh one is generated and written
    atomically with ``0600`` perms. No branch returns an empty token — the HTTP
    server never runs unauthenticated.
    """
    if cfg.http_token:
        return cfg.http_token, "env"
    path = cfg.http_token_file
    try:
        existing = path.read_text(encoding="utf-8").strip()
        if existing:
            return existing, "persisted"
    except OSError:
        pass
    token = secrets.token_urlsafe(32)
    _write_secret(path, token)
    return token, "generated"


def _write_secret(path: Path, value: str) -> None:
    """Atomically write a secret, ``0600`` (best-effort on Windows)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        try:
            os.fchmod(fd, stat.S_IRUSR | stat.S_IWUSR)  # 0600 before any content lands
        except (AttributeError, OSError):
            pass  # Windows lacks fchmod; the per-user home dir is the backstop
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(value + "\n")
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass


# ---- ASGI auth gate ---------------------------------------------------------

class BearerAuthMiddleware:
    """Pure-ASGI bearer-token gate.

    Deliberately *not* a Starlette ``BaseHTTPMiddleware`` — that one buffers the
    response, which deadlocks the MCP transport's streaming/SSE bodies. This
    wraps the ASGI app directly: it answers an unauthenticated liveness probe on
    ``health_path`` and rejects everything else without a valid token (deny by
    default), then hands authenticated requests through untouched.
    """

    def __init__(self, app, token: str, *, health_path: str = HEALTH_PATH):
        if not token:
            raise ValueError("BearerAuthMiddleware requires a non-empty token")
        self.app = app
        self._token = token.encode("utf-8")
        self.health_path = health_path

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        if scope.get("path", "") == self.health_path:
            await self._json(send, 200, {"status": "ok", "service": "memorised-them-all"})
            return
        if not self._authorized(scope):
            await self._json(send, 401,
                             {"error": "unauthorized", "detail": "missing or invalid bearer token"},
                             extra_headers=[(b"www-authenticate", b'Bearer realm="mta"')])
            return
        await self.app(scope, receive, send)

    def _authorized(self, scope) -> bool:
        for key, value in scope.get("headers") or ():
            if key == b"authorization":
                raw = value.decode("latin-1")
                if raw[:7].lower() == "bearer ":
                    # constant-time compare on bytes (tolerates any token charset)
                    return secrets.compare_digest(raw[7:].strip().encode("utf-8"), self._token)
                return False
        return False

    @staticmethod
    async def _json(send, status: int, obj: dict, *, extra_headers=()):
        body = json.dumps(obj).encode("utf-8")
        headers = [(b"content-type", b"application/json"),
                   (b"content-length", str(len(body)).encode()),
                   (b"cache-control", b"no-store")]
        headers.extend(extra_headers)
        await send({"type": "http.response.start", "status": status, "headers": headers})
        await send({"type": "http.response.body", "body": body})


# ---- app + security settings ------------------------------------------------

def _security_settings(cfg: Config, host: str, port: int):
    """Build the SDK's DNS-rebinding allowlist: the bound ``host:port`` (plus the
    loopback aliases when local), extended by any operator-supplied hosts/origins
    (which may use the SDK's ``base:*`` wildcard for reverse-proxy setups)."""
    from mcp.server.transport_security import TransportSecuritySettings

    hosts: set[str] = set()
    origins: set[str] = set()

    def add(h: str) -> None:
        hosts.add(f"{h}:{port}")
        origins.add(f"http://{h}:{port}")
        origins.add(f"https://{h}:{port}")

    add(host)
    if is_loopback(host):
        for alias in ("127.0.0.1", "localhost", "[::1]"):
            add(alias)
    hosts.update(_csv(cfg.http_allowed_hosts))
    origins.update(_csv(cfg.http_allowed_origins))
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=sorted(hosts),
        allowed_origins=sorted(origins),
    )


def build_app(cfg: Config, *, host: str, port: int, path: str, token: str):
    """Return the wrapped Streamable-HTTP ASGI app (auth gate + the SDK app with
    DNS-rebinding protection configured).

    Builds a *fresh* FastMCP via ``server.build_server()`` so this app owns its
    own session manager (one per process in production; rebuildable in tests).
    Importing ``server`` lazily keeps the module import-light and cycle-free."""
    from .server import build_server
    srv = build_server()
    srv.settings.host = host
    srv.settings.port = port
    srv.settings.streamable_http_path = path
    srv.settings.transport_security = _security_settings(cfg, host, port)
    return BearerAuthMiddleware(srv.streamable_http_app(), token, health_path=HEALTH_PATH)


def client_config(host: str, port: int, path: str, token: str) -> dict:
    """Render the connection recipe for HTTP MCP clients (the WP-24 seam)."""
    url = f"http://{host}:{port}{path}"
    return {
        "transport": "streamable-http",
        "url": url,
        "health": f"http://{host}:{port}{HEALTH_PATH}",
        "headers": {"Authorization": f"Bearer {token}"},
        "claude_code_add": (
            f'claude mcp add --transport http memorised-them-all {url} '
            f'--header "Authorization: Bearer {token}"'
        ),
        "mcp_json": {
            "memorised-them-all": {"url": url, "headers": {"Authorization": f"Bearer {token}"}}
        },
    }


# ---- serve ------------------------------------------------------------------

def serve(cfg: Config | None = None, *, transport: str = "stdio",
          host: str | None = None, port: int | None = None, path: str | None = None,
          allow_remote: bool | None = None, banner: bool = True) -> None:
    """Run the MCP server on the chosen transport. Blocks until the server stops.

    ``stdio`` (the default) delegates to ``server.main()`` unchanged. ``http``
    (alias ``streamable-http``) refuses a non-loopback bind unless ``allow_remote``,
    establishes the bearer token, and serves the auth-gated app via uvicorn.
    """
    cfg = cfg or load_config()
    if transport in (None, "stdio"):
        from .server import main as stdio_main
        return stdio_main()
    if transport not in ("http", "streamable-http"):
        raise ValueError(f"unknown transport: {transport!r}")

    host = host or cfg.http_host
    port = int(port or cfg.http_port)
    path = "/" + (path or cfg.http_path).strip().lstrip("/")
    allow_remote = cfg.http_allow_remote if allow_remote is None else allow_remote

    if not is_loopback(host) and not allow_remote:
        raise SystemExit(
            f"Refusing to bind the MCP HTTP transport to non-loopback host {host!r} "
            "without --allow-remote (or MTA_HTTP_ALLOW_REMOTE=on).\nBinding beyond "
            "127.0.0.1 exposes your local memory to the network — put a TLS reverse "
            "proxy in front of it first; see SECURITY.md.")

    token, source = resolve_token(cfg)
    app = build_app(cfg, host=host, port=port, path=path, token=token)
    if banner:
        _print_banner(host=host, port=port, path=path, token=token,
                      token_source=source, allow_remote=allow_remote)
    import uvicorn
    uvicorn.run(app, host=host, port=port, log_level="warning")


def _print_banner(*, host: str, port: int, path: str, token: str,
                  token_source: str, allow_remote: bool) -> None:
    """Echo the URL, token and a paste-ready client recipe to **stderr** (never a
    protocol channel; the token stays local)."""
    cc = client_config(host, port, path, token)
    lines = [
        "",
        "  Memorised them All — MCP server over Streamable HTTP",
        f"    URL:    {cc['url']}",
        f"    Token:  {token}   ({token_source})",
        f"    Health: {cc['health']}   (no auth; liveness only)",
        "",
        "  Connect from Claude Code:",
        f"    {cc['claude_code_add']}",
        "",
    ]
    if allow_remote and not is_loopback(host):
        lines += [
            "  ⚠ SECURITY: bound to a NON-loopback address. The bearer token is the",
            "    only thing guarding your local memory over the network. Terminate TLS",
            "    with a reverse proxy and never expose this on an untrusted network.",
            "",
        ]
    sys.stderr.write("\n".join(lines) + "\n")
    sys.stderr.flush()
