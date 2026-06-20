"""WP-91 — the .mcpb bundle must actually start on Windows (WIN-1).

The manifest declared win32 but ran `bash launch.sh`, and the cross-platform `launch.py`
was excluded from the bundle by .mcpbignore — so a Windows Claude Desktop install could not
start the server. These guard the fix structurally (the real Windows start is validated in
Claude Desktop, not here): launch.py ships, and the manifest runs it on win32 while keeping
the known-good bash launcher on POSIX.
"""
from __future__ import annotations

import json
import py_compile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def test_manifest_has_win32_override_running_launch_py():
    m = json.loads((REPO / "manifest.json").read_text(encoding="utf-8"))
    mc = m["server"]["mcp_config"]
    # POSIX default unchanged (known-good)
    assert mc["command"] == "bash"
    assert any("launch.sh" in a for a in mc["args"])
    # Windows override present and runs the cross-platform launcher
    ov = mc.get("platform_overrides", {}).get("win32")
    assert ov, "manifest missing win32 platform override → bundle can't start on Windows"
    assert ov["command"] == "python"
    assert any("launch.py" in a for a in ov["args"])
    assert "win32" in m["compatibility"]["platforms"]


def test_launch_py_ships_in_bundle_and_is_valid():
    # launch.py must NOT be excluded (it's the Windows entry point)
    ignore = (REPO / ".mcpbignore").read_text(encoding="utf-8").splitlines()
    assert "launch.py" not in [ln.strip() for ln in ignore], \
        "launch.py is excluded by .mcpbignore → it won't ship → Windows can't start"
    launcher = REPO / "launch.py"
    assert launcher.exists()
    py_compile.compile(str(launcher), doraise=True)   # stdlib-only, must parse/compile
