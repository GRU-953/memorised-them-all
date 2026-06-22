"""Dependency preflight scanner + guided remediation — powers `mta doctor` (R3).

Reports each runtime dependency as present-&-current / outdated / missing with
**detected-vs-required** versions, and proposes argv-only, idempotent remediation
per platform. `mta doctor --fix` applies only the safe pip upgrades; system-tool
installs (brew/apt/dnf/pacman/winget/…) are *suggested*, never auto-run with
sudo, so a no-admin box degrades gracefully.
"""
from __future__ import annotations

import importlib.metadata as _md
import os
import re
import shutil
import subprocess
import sys
import sysconfig

from .config import Config
from .platform import bootstrap_path

_PKG = "memorised-them-all"
_SYSTEM_BINS = ("tesseract", "ffmpeg")

# Plain-English failure-symptom catalogue (WP-153), keyed on what a NON-TECHNICAL user
# actually sees — in their AI app or terminal — not on internal error names. `mta doctor`
# prints this so the people most likely to get stuck (who can't read a stack trace) get a
# human next step. Deliberately short and jargon-light.
SYMPTOMS: list[dict] = [
    {"symptom": "My AI assistant says it doesn't have the memorise / recall tool.",
     "cause": "The local server isn't registered in that app yet, or the app wasn't restarted.",
     "fix": "Run `mta setup`, then FULLY quit and reopen the AI app (not just close the window)."},
    {"symptom": "I typed `mta` and got “command not found” / “not recognized”.",
     "cause": "Python's scripts folder isn't on your PATH.",
     "fix": "Run it as `python -m mta` (Windows: `py -m mta`) — or see the PATH line above."},
    {"symptom": "`mta` complains about a missing/old package (numpy, markitdown, …).",
     "cause": "A dependency is missing or out of date.",
     "fix": "Run `mta doctor --fix` (safe pip upgrades), or `pip install -U memorised-them-all`."},
    {"symptom": "Scanned PDFs or images come out empty.",
     "cause": "OCR (Tesseract) isn't installed — optional, only needed for scans/images.",
     "fix": "Install Tesseract via your package manager (see the suggestion above), then re-digest."},
    {"symptom": "Digest said it “found no files”.",
     "cause": "The folder path was wrong or empty.",
     "fix": "Copy the folder's real path (Finder: right-click → hold Option → Copy as Pathname; "
            "Explorer: Shift-right-click → Copy as path) and digest that."},
    {"symptom": "Recall says there's no memory / nothing to search.",
     "cause": "Nothing has been digested into this project yet.",
     "fix": "Digest a folder first (`mta digest <folder>`), then ask again."},
    {"symptom": "Windows: “Windows protected your PC” when launching the installer.",
     "cause": "The download is unsigned (we don't ship a paid certificate).",
     "fix": "Click “More info” → “Run anyway”. To avoid it entirely, install via pip/winget."},
    {"symptom": "macOS: “… can't be opened because Apple cannot check it”.",
     "cause": "The app isn't notarized (we don't ship a paid Apple identity).",
     "fix": "Right-click the app → Open (once), or System Settings → Privacy & Security → "
            "“Open Anyway”. To avoid it entirely, install via Homebrew or pipx."},
    {"symptom": "I use the app with no terminal (e.g. Claude Desktop) — how do I check health?",
     "cause": "You don't need the terminal.",
     "fix": "Ask your AI to run the `memory_status` tool — it reports the same health, in-app."},
]


def _scripts_dir() -> str:
    """Where the `mta` console script lives (…/bin on POSIX, …\\Scripts on Windows)."""
    try:
        return sysconfig.get_path("scripts") or ""
    except Exception:  # noqa: BLE001
        return ""


def path_status() -> dict:
    """Is the `mta` console script reachable on PATH? The #1 post-install novice failure is
    "installed, but `command not found`" because the user-scripts dir isn't on PATH. When the
    package is installed but `mta` doesn't resolve, return a one-line, OS-specific fix (plus
    the always-works `python -m mta` fallback). Running from source (not installed) is not
    flagged — that's a developer, not a stuck novice."""
    installed = _installed_version(_PKG) is not None
    resolved = shutil.which("mta")
    on_path = resolved is not None
    sd = _scripts_dir()
    fix = None
    if installed and not on_path:
        if os.name == "nt":
            fix = (f"`mta` is installed but not on PATH. Run it as `py -m mta`, or add "
                   f'"{sd}" to PATH (Settings → Edit the system environment variables).')
        else:
            fix = (f"`mta` is installed but not on PATH. Run it as `{sys.executable} -m mta`, "
                   f'or add it: export PATH="{sd}:$PATH"')
    return {"installed": installed, "on_path": on_path, "resolved": resolved,
            "scripts_dir": sd, "fix": fix,
            "status": "ok" if (on_path or not installed) else "warn"}


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


def plain_report(result: dict, path: dict, plan: list[dict], applied: list[dict]) -> list[str]:
    """Human-readable, non-technical summary lines for `mta doctor` (WP-153). Leads with a
    one-line verdict, then each concrete issue + its plain fix, then the PATH check, then the
    'common problems' catalogue keyed on what the user sees."""
    lines: list[str] = []
    issues = [d for d in result["python"] if d["status"] != "ok"] + \
             [b for b in result["binaries"] if not b["present"]]
    healthy = not issues and path["status"] == "ok"
    lines.append("✅ Everything looks healthy." if healthy
                 else f"⚠ Found {len(issues) + (0 if path['status'] == 'ok' else 1)} thing(s) to look at.")
    for d in result["python"]:
        if d["status"] == "missing":
            lines.append(f"• Python package “{d['name']}” is missing → run `mta doctor --fix`.")
        elif d["status"] == "outdated":
            lines.append(f"• Python package “{d['name']}” is out of date "
                         f"(have {d.get('installed', '?')}, need {d.get('required', '?')}) "
                         "→ run `mta doctor --fix`.")
    for b in result["binaries"]:
        if not b["present"]:
            lines.append(f"• Optional tool “{b['name']}” not found "
                         f"(only needed for {'scanned-document OCR' if b['name'] == 'tesseract' else 'media'}) "
                         "— install it via your package manager if you need it.")
    if path["fix"]:
        lines.append(f"• {path['fix']}")
    for c in plan:
        if not c.get("auto") and c.get("argv"):
            lines.append("  suggested (not auto-run): " + " ".join(c["argv"]))
        elif not c.get("auto") and c.get("hint"):
            lines.append("  suggestion: " + c["hint"])
    if applied:
        ok = sum(1 for a in applied if a.get("ok"))
        lines.append(f"Applied {ok}/{len(applied)} automatic fix(es).")
    lines.append("")
    lines.append("Common problems (what you might see → what to do):")
    for s in SYMPTOMS:
        lines.append(f"  • {s['symptom']}")
        lines.append(f"      → {s['fix']}")
    return lines


def doctor(cfg: Config | None = None, fix: bool = False, dry_run: bool = False) -> dict:
    """Scan + report; with fix (and not dry_run) apply ONLY the safe pip upgrades.
    Idempotent and re-runnable; system-tool installs are always suggested, never
    auto-run with admin rights. Includes a PATH check + a plain-English report + the
    failure-symptom catalogue (WP-153)."""
    result = scan(cfg)
    plan = remediation(result)
    path = path_status()
    applied: list[dict] = []
    if fix and not dry_run:
        for c in plan:
            if c.get("auto") and c.get("argv"):
                applied.append({"argv": c["argv"], "ok": _run(c["argv"])})
    report = plain_report(result, path, plan, applied)
    return {"status": "ok", "scan": result, "path": path, "remediation": plan,
            "applied": applied, "symptoms": SYMPTOMS, "report": report,
            "dry_run": dry_run, "all_ok": result["all_ok"]}
