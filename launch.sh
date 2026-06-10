#!/usr/bin/env bash
# MCP launcher — what Claude Desktop / Claude Code execute to start the server.
# Fast path: ensure the venv + Python deps exist (so `mta.server` imports), then
# start the server immediately. Optional system tools (Tesseract, unar) install in the
# BACKGROUND so the server is responsive at once (the engine is model-free, so there is
# nothing to download before it works).
set -uo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$DIR/.venv"
STATE="${MTA_HOME:-$HOME/.memorised-them-all}/state"

needs_bootstrap=0
[ -x "$VENV/bin/python" ] || needs_bootstrap=1
"$VENV/bin/python" -c "import mta, mcp" >/dev/null 2>&1 || needs_bootstrap=1

if [ "$needs_bootstrap" = "1" ]; then
  # Synchronous, lightweight: ensure the venv + Python deps exist so the server imports.
  bash "$DIR/install.sh" >&2 || true
fi

# First ever run: kick the full install (optional system tools) in the background.
if [ ! -f "$STATE/installed" ]; then
  ( bash "$DIR/install.sh" >/dev/null 2>&1 & ) >/dev/null 2>&1
fi

# Run from the source tree via PYTHONPATH so the server starts even if an
# editable install didn't register the package (belt-and-suspenders).
exec env PYTHONPATH="$DIR${PYTHONPATH:+:$PYTHONPATH}" "$VENV/bin/python" -m mta.server
