"""``mta`` command-line interface — the same engine, without Claude.

Subcommands:
  mta digest <paths…> [--project P] [--reset]   build/refresh memory locally
  mta recall "<query>" [--project P] [-k N]      query memory (small slice)
  mta overview [--project P]                     synopsis + themes
  mta export <dest> [--project P]                export portable markdown
  mta status                                     local stack health
  mta mindmap [--project P] [--open]             path to the mind map
  mta update [--force]                           update MarkItDown + deps
  mta doctor [--fix] [--dry-run]                 scan deps; suggest or apply fixes
  mta serve [--http | --rest] [--host H] [--port N]  run the server (stdio; --http=MCP HTTP; --rest=JSON gateway)
  mta export-schema [--format F] [--out DIR]     export tool schemas (OpenAI/Gemini/OpenAPI 3.1)
  mta recipes [--format text|json]               per-client connection recipes (every surface)
  mta setup-claude [--env KEY=VALUE]             register this server in Claude's config (Desktop + Code)
"""
from __future__ import annotations

import argparse
import json

from .core import recall as recall_mod
from .core import render, store, updater
from .core.config import load as load_config
from .core.digest import digest as run_digest


def _print(obj) -> None:
    print(json.dumps(obj, indent=2, ensure_ascii=False))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="mta",
                                description="Memorised them All — local, token-free file digestion & graph memory.")
    p.add_argument("--project", default=None, help="named, reusable memory")
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("digest", help="convert + digest files/dirs/globs")
    d.add_argument("paths", nargs="+")
    d.add_argument("--reset", action="store_true")
    d.add_argument("--fast", action="store_true",
                   help="skip the LLM (classical extraction); faster, fully deterministic")

    cv = sub.add_parser("convert", help="convert files/dirs/globs to Markdown (legacy Bengali→Unicode)")
    cv.add_argument("paths", nargs="+")
    cv.add_argument("--out", default=None,
                    help="output dir (default: markdown_converted/ beside the input)")

    r = sub.add_parser("recall", help="query the memory")
    r.add_argument("query")
    r.add_argument("-k", type=int, default=0)

    sub.add_parser("overview", help="synopsis + themes")

    e = sub.add_parser("export", help="export portable markdown")
    e.add_argument("dest")

    sub.add_parser("status", help="local stack health")

    m = sub.add_parser("mindmap", help="path to the offline mind map")
    m.add_argument("--open", action="store_true")

    u = sub.add_parser("update", help="update MarkItDown + dependencies")
    u.add_argument("--force", action="store_true")

    dr = sub.add_parser("doctor", help="scan dependencies; suggest or apply fixes")
    dr.add_argument("--fix", action="store_true", help="apply safe (pip) upgrades")
    dr.add_argument("--dry-run", action="store_true", help="only show what would change")

    sub.add_parser("forget", help="delete a project's memory (irreversible)")

    sv = sub.add_parser("serve", help="run the MCP server (stdio by default; --http/--rest = HTTP surfaces)")
    mode = sv.add_mutually_exclusive_group()
    mode.add_argument("--http", action="store_true",
                      help="serve over MCP Streamable HTTP instead of stdio (opt-in; loopback + bearer token)")
    mode.add_argument("--rest", action="store_true",
                      help="serve the plain-JSON REST gateway (opt-in; loopback + bearer token; POST /tools/{name})")
    sv.add_argument("--host", default=None, help="HTTP bind host (default 127.0.0.1)")
    sv.add_argument("--port", type=int, default=None, help="HTTP bind port (default 8765)")
    sv.add_argument("--path", default=None, help="MCP HTTP endpoint path (--http only; default /mcp)")
    sv.add_argument("--allow-remote", action="store_true",
                    help="permit a non-loopback bind (exposes the server beyond this machine)")

    es = sub.add_parser("export-schema",
                        help="export tool schemas for other AIs (OpenAI/Gemini/OpenAPI)")
    es.add_argument("--format", choices=["openai", "gemini", "openapi", "all"],
                    default="all", help="schema dialect to emit (default: all)")
    es.add_argument("--out", default=None,
                    help="write <format>.json into this directory (default: print to stdout)")

    rc = sub.add_parser("recipes",
                        help="print per-client connection recipes (Claude / HTTP / REST / OpenAI / Gemini)")
    rc.add_argument("--host", default=None, help="HTTP host for the recipes (default 127.0.0.1)")
    rc.add_argument("--port", type=int, default=None, help="HTTP port for the recipes (default 8765)")
    rc.add_argument("--format", choices=["text", "json"], default="text",
                    help="output format (default: text)")

    scl = sub.add_parser("setup-claude",
                         help="register this MCP server in Claude's config (Desktop + Code)")
    scl.add_argument("--env", action="append", default=[], metavar="KEY=VALUE",
                     help="extra MTA_* env to bake into the server entry (repeatable)")

    args = p.parse_args(argv)

    # setup-claude only writes the host's Claude config — no engine wiring needed.
    if args.cmd == "setup-claude":
        from .core.setup import setup_claude, render_summary
        env = {}
        for kv in args.env:
            k, _, v = kv.partition("=")
            if k.strip():
                env[k.strip()] = v
        result = setup_claude(env=env or None)
        print(render_summary(result))
        return 0

    # export-schema is pure + offline (it only reads the in-process tool registry),
    # so it needs no config load or PATH bootstrap — dispatch before the engine wiring.
    if args.cmd == "export-schema":
        from .interop import schemas
        data = schemas.export(args.format)
        if args.out:
            written = schemas.write_files(data, args.out, args.format)
            _print({"status": "ok", "format": args.format,
                    "written": [str(w) for w in written]})
        else:
            _print(data)
        return 0

    # recipes are pure/offline too (formatting only) — dispatch before engine wiring.
    if args.cmd == "recipes":
        from .interop import recipes as _recipes
        data = _recipes.build(host=args.host, port=args.port)
        if args.format == "json":
            _print(data)
        else:
            print(_recipes.render_text(data))
        return 0

    from .core.platform import bootstrap_path
    bootstrap_path()
    cfg = load_config().with_project(args.project)

    if args.cmd == "digest":
        _print(run_digest(cfg, args.paths, reset=args.reset, fast=args.fast))
    elif args.cmd == "convert":
        from .core.digest import convert_to_markdown
        _print(convert_to_markdown(cfg, args.paths, out_dir=args.out))
    elif args.cmd == "recall":
        _print(recall_mod.recall(cfg, args.query, k=args.k or None))
    elif args.cmd == "overview":
        _print(recall_mod.overview(cfg))
    elif args.cmd == "export":
        _print(render.export_bundle(cfg, args.dest))
    elif args.cmd == "status":
        from .server import _status
        _print(_status())
    elif args.cmd == "mindmap":
        if not cfg.mindmap_html.exists():
            _print({"status": "no_memory", "project": cfg.project})
        else:
            if args.open:
                import webbrowser  # portable across macOS/Linux/Windows
                webbrowser.open(cfg.mindmap_html.as_uri())
            _print({"status": "ok", "path": str(cfg.mindmap_html)})
    elif args.cmd == "forget":
        _print(store.delete_project(cfg))
    elif args.cmd == "update":
        _print(updater.run_check(cfg, force=args.force))
    elif args.cmd == "doctor":
        from .core import deps
        _print(deps.doctor(cfg, fix=args.fix, dry_run=args.dry_run))
    elif args.cmd == "serve":
        if args.http:
            from .transport import serve as serve_transport
            serve_transport(cfg, transport="http", host=args.host, port=args.port,
                            path=args.path, allow_remote=args.allow_remote or None)
        elif args.rest:
            from .interop.rest import serve as serve_rest
            serve_rest(cfg, host=args.host, port=args.port,
                       allow_remote=args.allow_remote or None)
        else:
            from .server import main as serve_main
            serve_main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
