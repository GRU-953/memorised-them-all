#!/usr/bin/env python3
"""Cross-platform launcher/bootstrap (standard library only).

Works on macOS, Linux and Windows. Ensures a local virtualenv with the package's
dependencies exists (handling the ``Scripts/`` vs ``bin/`` layout difference),
then starts the MCP server. This is the portable equivalent of ``launch.sh`` —
on Windows, configure your MCP client to run ``python launch.py``.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"


def _venv_python(venv: Path) -> Path:
    return venv / ("Scripts" if os.name == "nt" else "bin") / (
        "python.exe" if os.name == "nt" else "python")


def _ensure_venv() -> Path:
    py = _venv_python(VENV)
    ready = py.exists()
    if ready:
        try:
            subprocess.run([str(py), "-c", "import mta, mcp"], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            ready = False
    if not ready:
        import venv as _venv
        print("[mta] first-run setup — building local environment…", file=sys.stderr)
        _venv.EnvBuilder(with_pip=True).create(str(VENV))
        py = _venv_python(VENV)
        subprocess.run([str(py), "-m", "pip", "install", "-q", "-U", "pip", "wheel"],
                       check=False)
        req = ROOT / "requirements.txt"
        if req.exists():
            subprocess.run([str(py), "-m", "pip", "install", "-q", "-r", str(req)],
                           check=False)
        # Install the package (for the `mta` entry point) and auto-configure every
        # detected AI client on this machine — the Windows equivalent of install.sh
        # step 4. Best-effort: a setup hiccup must never block the server from starting.
        subprocess.run([str(py), "-m", "pip", "install", "-q", "-e", str(ROOT)], check=False)
        if os.environ.get("MTA_SKIP_SETUP", os.environ.get("MTA_SKIP_CLAUDE_SETUP", "0")) != "1":
            env = dict(os.environ)
            env["PYTHONPATH"] = str(ROOT) + (
                os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
            try:
                subprocess.run([str(py), "-m", "mta.cli", "setup"], env=env,
                               timeout=300, check=False)
            except Exception:  # noqa: BLE001 - setup is best-effort; never block startup
                pass
    return py


def main() -> None:
    py = _ensure_venv()
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT) + (
        os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    args = [str(py), "-m", "mta.server"]
    if os.name == "nt":  # no os.execve on Windows — spawn and mirror exit code
        raise SystemExit(subprocess.call(args, env=env))
    os.execve(str(py), args, env)


if __name__ == "__main__":
    main()
