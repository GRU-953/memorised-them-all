#!/usr/bin/env python3
"""Assert the version is single-sourced.

`mta/__init__.py:__version__` is the one canonical version (pyproject derives it
via hatchling `dynamic`). Every other manifest that hard-codes a version must
agree. Run in CI; exit 1 on any drift.

Optionally pass a git tag as argv[1] (e.g. "v1.3.4") to also enforce the
tag == version gate used by the release workflow.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _canonical() -> str:
    txt = (ROOT / "mta" / "__init__.py").read_text(encoding="utf-8")
    m = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', txt)
    if not m:
        sys.exit("FAIL: no __version__ found in mta/__init__.py")
    return m.group(1)


def _collect(canonical: str) -> dict[str, str]:
    out = {"mta/__init__.py": canonical}
    out["manifest.json"] = json.loads(
        (ROOT / "manifest.json").read_text(encoding="utf-8"))["version"]
    out[".claude-plugin/plugin.json"] = json.loads(
        (ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))["version"]
    mk = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    out[".claude-plugin/marketplace.json (metadata.version)"] = mk["metadata"]["version"]
    cff = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
    m = re.search(r'^version:\s*["\']?([^"\'\n]+?)["\']?\s*$', cff, re.M)
    out["CITATION.cff"] = m.group(1).strip() if m else "<missing>"
    sj = json.loads((ROOT / "server.json").read_text(encoding="utf-8"))
    out["server.json (version)"] = sj["version"]
    out["server.json (packages[0].version)"] = sj["packages"][0]["version"]
    return out


def main() -> int:
    canonical = _canonical()
    versions = _collect(canonical)
    drift = {f: v for f, v in versions.items() if v != canonical}
    for f, v in versions.items():
        print(f"  {'ok   ' if v == canonical else 'DRIFT'} {f}: {v}")
    if drift:
        print(f"\nFAIL: version drift vs canonical {canonical!r}: {drift}", file=sys.stderr)
        return 1
    tag = sys.argv[1] if len(sys.argv) > 1 else ""
    if tag:
        if tag.lstrip("v").strip() != canonical:
            print(f"\nFAIL: git tag {tag!r} does not match version {canonical!r}", file=sys.stderr)
            return 1
        print(f"  ok    git tag {tag} matches version {canonical}")
    print(f"\nOK: all version strings agree at {canonical}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
