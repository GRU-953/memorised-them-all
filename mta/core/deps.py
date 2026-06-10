"""Dependency preflight scanner + guided remediation — powers `mta doctor` (R3).

Reports each runtime dependency as present-&-current / outdated / missing with
**detected-vs-required** versions, and proposes argv-only, idempotent remediation
per platform. `mta doctor --fix` applies only the safe pip upgrades; system-tool
installs (brew/apt/dnf/pacman/winget/…) are *suggested*, never auto-run with
sudo, so a no-admin box degrades gracefully.
"""
from __future__ import annotations

import importlib.metadata as _md
import re
import shutil
import subprocess
import sys

from .config import Config
from .platform import bootstrap_path

_PKG = "memorised-them-all"
_SYSTEM_BINS = ("tesseract", "ffmpeg")


def _vtuple(s) -> tuple:
    """Leading numeric version tuple, e.g. '1.26.4rc1' -> (1, 26, 4)."""
    out = []
    for seg in str(s).split("."):
        m = re.match(r"\d+", seg)
        if not m:
            break
        out.append(int(m.group()))
    return tuple(out)


def _installed_version(name: str) -> str | None:
    try:
        return _md.version(name)
    except Exception:  # noqa: BLE001 - PackageNotFoundError or odd metadata
        return None


def _parse_req(spec: str) -> tuple[str, str | None, bool]:
    """(name, min_version|None, is_optional) from a Requires-Dist specifier."""
    optional = "extra ==" in spec or "extra==" in spec
    head = spec.split(";", 1)[0].strip()
    name_m = re.match(r"^([A-Za-z0-9._-]+)", head)
    name = name_m.group(1) if name_m else head
    min_m = re.search(r">=\s*([0-9][0-9A-Za-z.\-]*)", head)
    return name, (min_m.group(1) if min_m else None), optional


def _bin_version(path: str) -> str | None:
    try:
        r = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=5)
        line = ((r.stdout or "") + (r.stderr or "")).strip().splitlines()
        if line:
            m = re.search(r"\d+\.\d+(?:\.\d+)?", line[0])
            return m.group(0) if m else line[0][:40]
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def scan(cfg: Config | None = None, probe_bin_versions: bool = True) -> dict:
    """Scan Python deps (vs the package's Requires-Dist) and the system binaries."""
    bootstrap_path()
    python: list[dict] = []
    try:
        reqs = _md.requires(_PKG) or []
    except Exception:  # noqa: BLE001 - running from source without an installed dist
        reqs = []
    for spec in reqs:
        name, minv, optional = _parse_req(spec)
        if optional:  # extras (graph/mlx/dev) aren't required for the core engine
            continue
        inst = _installed_version(name)
        if inst is None:
            status = "missing"
        elif minv and _vtuple(inst) < _vtuple(minv):
            status = "outdated"
        else:
            status = "ok"
        python.append({"name": name, "required": (">=" + minv) if minv else "any",
                       "installed": inst, "status": status})

    binaries: list[dict] = []
    for b in _SYSTEM_BINS:
        p = shutil.which(b)
        binaries.append({"name": b, "present": p is not None, "path": p,
                         "version": (_bin_version(p) if (p and probe_bin_versions) else None),
                         "status": "ok" if p else "missing"})

    counts = {"ok": 0, "outdated": 0, "missing": 0}
    for item in python + binaries:
        counts[item["status"]] = counts.get(item["status"], 0) + 1
    return {"python": python, "binaries": binaries, "summary": counts,
            "all_ok": counts["outdated"] == 0 and counts["missing"] == 0}


def remediation(result: dict) -> list[dict]:
    """Argv-only commands to fix outdated/missing items. Python → pip (safe, run on
    --fix); system tools → the right manager, *suggested only* (never auto-sudo)."""
    import platform as _plat
    cmds: list[dict] = []
    py_fix = [d["name"] for d in result["python"] if d["status"] != "ok"]
    if py_fix:
        cmds.append({"for": "python", "argv": [sys.executable, "-m", "pip", "install", "-U", *py_fix],
                     "auto": True, "needs_admin": False})
    missing_bins = [b["name"] for b in result["binaries"] if not b["present"]]
    if missing_bins:
        if shutil.which("brew"):
            cmds.append({"for": "system", "argv": ["brew", "install", *missing_bins],
                         "auto": False, "needs_admin": False})
        elif shutil.which("apt-get"):
            pkgs = ["tesseract-ocr" if m == "tesseract" else m for m in missing_bins]
            cmds.append({"for": "system", "argv": ["sudo", "apt-get", "install", "-y", *pkgs],
                         "auto": False, "needs_admin": True})
        elif shutil.which("dnf"):
            cmds.append({"for": "system", "argv": ["sudo", "dnf", "install", "-y", *missing_bins],
                         "auto": False, "needs_admin": True})
        elif shutil.which("pacman"):
            cmds.append({"for": "system", "argv": ["sudo", "pacman", "-S", "--noconfirm", *missing_bins],
                         "auto": False, "needs_admin": True})
        elif shutil.which("winget"):
            cmds.append({"for": "system", "argv": ["winget", "install", *missing_bins],
                         "auto": False, "needs_admin": False})
        else:
            cmds.append({"for": "system", "argv": None, "auto": False, "needs_admin": False,
                         "hint": "install " + ", ".join(missing_bins) + " via your package manager"})
    return cmds


def _run(argv: list[str]) -> bool:
    try:
        return subprocess.run(argv, timeout=1800).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def doctor(cfg: Config | None = None, fix: bool = False, dry_run: bool = False) -> dict:
    """Scan + report; with fix (and not dry_run) apply ONLY the safe pip upgrades.
    Idempotent and re-runnable; system-tool installs are always suggested, never
    auto-run with admin rights."""
    result = scan(cfg)
    plan = remediation(result)
    applied: list[dict] = []
    if fix and not dry_run:
        for c in plan:
            if c.get("auto") and c.get("argv"):
                applied.append({"argv": c["argv"], "ok": _run(c["argv"])})
    return {"status": "ok", "scan": result, "remediation": plan,
            "applied": applied, "dry_run": dry_run, "all_ok": result["all_ok"]}
