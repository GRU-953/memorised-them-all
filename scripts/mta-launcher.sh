#!/usr/bin/env bash
# CLI launcher used by the Homebrew formula. Bootstraps a self-managed virtualenv
# (under MTA_HOME) on first run — Homebrew's build sandbox forbids network, so we
# install dependencies at runtime instead — then runs the `mta` CLI directly from
# the source tree via PYTHONPATH (the package is pure-Python; no build step, so it
# is robust even when packagers strip README/LICENSE from the install tree).
set -uo pipefail
REPO="${MTA_REPO:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
export MTA_HOME="${MTA_HOME:-$HOME/.memorised-them-all}"
VENV="$MTA_HOME/venv"
mkdir -p "$MTA_HOME"

ready=1
{ [ -x "$VENV/bin/python" ] && "$VENV/bin/python" -c "import numpy, networkx, rapidfuzz, mcp" >/dev/null 2>&1; } || ready=0
if [ "$ready" != "1" ]; then
  for p in python3.12 python3.11 python3; do command -v "$p" >/dev/null 2>&1 && PY=$p && break; done
  : "${PY:?Python 3 not found}"
  echo "[mta] first-run setup — building local environment…" >&2
  "$PY" -m venv "$VENV"
  "$VENV/bin/python" -m pip -q install -U pip wheel >/dev/null 2>&1 || true
  "$VENV/bin/python" -m pip -q install -r "$REPO/requirements.txt" >&2 || \
    echo "[mta] some deps failed to install; the engine still runs with fallbacks." >&2
  # The pinned PyPI MarkItDown (installed above) is the offline-correct baseline.
  # Pulling the latest UPSTREAM commit is opt-in (MTA_MARKITDOWN_UPSTREAM=on or
  # MTA_AUTO_UPDATE=upstream) and runs in the background so it never blocks startup.
  if [ "${MTA_MARKITDOWN_UPSTREAM:-off}" = "on" ] || [ "${MTA_AUTO_UPDATE:-on}" = "upstream" ]; then
    ( "$VENV/bin/python" -m pip -q install -U \
        "markitdown[pdf,docx,pptx,xlsx,xls,outlook] @ git+https://github.com/microsoft/markitdown.git#subdirectory=packages/markitdown" \
        >/dev/null 2>&1 & )
  fi
fi
exec env PYTHONPATH="$REPO${PYTHONPATH:+:$PYTHONPATH}" "$VENV/bin/python" -m mta.cli "$@"
