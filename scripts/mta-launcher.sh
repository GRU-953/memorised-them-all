#!/usr/bin/env bash
# CLI launcher used by the Homebrew formula. Bootstraps a self-managed virtualenv
# (under MTA_HOME) on first run — Homebrew's build sandbox forbids network, so we
# install dependencies at runtime instead — then execs the `mta` CLI.
set -uo pipefail
REPO="${MTA_REPO:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
export MTA_HOME="${MTA_HOME:-$HOME/.memorised-them-all}"
VENV="$MTA_HOME/venv"
mkdir -p "$MTA_HOME"

ready=1
{ [ -x "$VENV/bin/python" ] && "$VENV/bin/python" -c "import mta" >/dev/null 2>&1; } || ready=0
if [ "$ready" != "1" ]; then
  for p in python3.12 python3.11 python3; do command -v "$p" >/dev/null 2>&1 && PY=$p && break; done
  : "${PY:?Python 3 not found}"
  echo "[mta] first-run setup…" >&2
  "$PY" -m venv "$VENV"
  "$VENV/bin/python" -m pip -q install -U pip wheel >/dev/null 2>&1 || true
  "$VENV/bin/python" -m pip -q install "$REPO" >&2 || \
    "$VENV/bin/python" -m pip -q install memorised-them-all >&2
  # Upgrade to the latest upstream MarkItDown in the background.
  ( "$VENV/bin/python" -m pip -q install -U \
      "markitdown[pdf,docx,pptx,xlsx,xls,outlook] @ git+https://github.com/microsoft/markitdown.git#subdirectory=packages/markitdown" \
      >/dev/null 2>&1 & )
fi
exec "$VENV/bin/python" -m mta.cli "$@"
