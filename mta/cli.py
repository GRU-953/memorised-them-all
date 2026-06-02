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
  mta serve                                      run the MCP server (stdio)
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

    sub.add_parser("serve", help="run the MCP server (stdio)")

    args = p.parse_args(argv)
    from .core.platform import bootstrap_path
    bootstrap_path()
    cfg = load_config().with_project(args.project)

    if args.cmd == "digest":
        _print(run_digest(cfg, args.paths, reset=args.reset, fast=args.fast))
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
        from .server import main as serve_main
        serve_main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
