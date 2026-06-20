#!/usr/bin/env bash
# Memorised them All — idempotent installer.
# Sets up a Python venv with MarkItDown (pinned PyPI by default; upstream is opt-in),
# installs optional system tools (Tesseract OCR + language packs, unar for rar archives),
# and registers the MCP server in Claude. The engine is deterministic and model-free —
# there are NO AI models to download. Safe to re-run; only does missing work. Works on
# macOS and Linux (Windows uses launch.py).
set -uo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$DIR/.venv"
STATE="${MTA_HOME:-$HOME/.memorised-them-all}/state"
mkdir -p "$STATE"
log() { printf '\033[1;35m[mta]\033[0m %s\n' "$*" >&2; }

# --- 1. Python venv (prefer 3.12 — 3.14 has missing wheels) ----------------
pick_python() {
  for p in python3.12 python3.11 python3.10 python3; do
    command -v "$p" >/dev/null 2>&1 && { echo "$p"; return; }
  done
  echo ""
}
if [ ! -x "$VENV/bin/python" ]; then
  PY="$(pick_python)"
  if [ -z "$PY" ] && command -v brew >/dev/null 2>&1; then
    log "Installing python@3.12 via Homebrew…"; brew install python@3.12 || true
    PY="$(pick_python)"
  fi
  [ -z "$PY" ] && { log "No Python 3 found."; exit 1; }
  log "Creating venv with $PY"
  "$PY" -m venv "$VENV" || exit 1
fi
PYBIN="$VENV/bin/python"
"$PYBIN" -m pip install --quiet --upgrade pip wheel >/dev/null 2>&1 || true

# --- 2. Python dependencies ------------------------------------------------
log "Installing Python dependencies…"
"$PYBIN" -m pip install --quiet -r "$DIR/requirements.txt" || \
  log "Some core deps failed — the engine still runs with fallbacks."

# Baseline MarkItDown is the pinned PyPI build (installed from requirements.txt
# above) so the first run works offline and reproducibly. Pulling the LATEST
# upstream commit is opt-in and needs network: MTA_MARKITDOWN_UPSTREAM=on (or
# MTA_AUTO_UPDATE=upstream).
_up="${MTA_MARKITDOWN_UPSTREAM:-off}"
if [ "$_up" = "on" ] || [ "$_up" = "1" ] || [ "$_up" = "true" ] || [ "$_up" = "yes" ] \
   || [ "${MTA_AUTO_UPDATE:-on}" = "upstream" ]; then
  log "Pulling latest upstream MarkItDown (opt-in)…"
  "$PYBIN" -m pip install --quiet -U \
    "markitdown[pdf,docx,pptx,xlsx,xls,outlook] @ git+https://github.com/microsoft/markitdown.git#subdirectory=packages/markitdown" \
    || log "Upstream MarkItDown pull failed; the PyPI MarkItDown remains in use."
else
  log "Using the pinned PyPI MarkItDown (offline-correct); set MTA_MARKITDOWN_UPSTREAM=on for the latest upstream build."
fi

"$PYBIN" -m pip install --quiet "python-igraph>=0.11" "leidenalg>=0.10" >/dev/null 2>&1 \
  && log "Enabled Leiden community detection." || \
  log "Leiden unavailable — using NetworkX Louvain (fine)."

# Install the package itself (provides the `mta` entry point).
"$PYBIN" -m pip install --quiet -e "$DIR" >/dev/null 2>&1 || true

# --- 3. System applications (Homebrew on macOS/Linux; native pkg mgrs on Linux) ----
# A non-interactive sudo helper: only elevates if it won't block on a password.
SUDO=""
if [ "$(id -u 2>/dev/null)" != "0" ] && command -v sudo >/dev/null 2>&1 && sudo -n true 2>/dev/null; then
  SUDO="sudo -n"
fi
if command -v brew >/dev/null 2>&1; then
  for app in tesseract ffmpeg unar; do
    command -v "$app" >/dev/null 2>&1 || { log "brew install $app"; brew install "$app" || true; }
  done
  # Many OCR languages (incl. Bengali) + igraph C lib for python-igraph.
  brew list tesseract-lang >/dev/null 2>&1 || brew install tesseract-lang >/dev/null 2>&1 || true
elif command -v apt-get >/dev/null 2>&1 && [ -n "$SUDO$( [ "$(id -u)" = 0 ] && echo root )" ]; then
  log "Installing system apps via apt…"
  $SUDO apt-get update -y >/dev/null 2>&1 || true
  $SUDO apt-get install -y tesseract-ocr tesseract-ocr-all ffmpeg unar >/dev/null 2>&1 || true
elif command -v dnf >/dev/null 2>&1 && [ -n "$SUDO$( [ "$(id -u)" = 0 ] && echo root )" ]; then
  log "Installing system apps via dnf…"
  $SUDO dnf install -y tesseract tesseract-langpack-eng tesseract-langpack-ben ffmpeg unar >/dev/null 2>&1 || true
elif command -v pacman >/dev/null 2>&1 && [ -n "$SUDO$( [ "$(id -u)" = 0 ] && echo root )" ]; then
  log "Installing system apps via pacman…"
  $SUDO pacman -S --noconfirm tesseract tesseract-data-eng tesseract-data-ben ffmpeg unarchiver >/dev/null 2>&1 || true
else
  log "No usable package manager (or sudo unavailable) — install Tesseract/ffmpeg/unar manually for OCR + rar support."
fi

# --- 4. Auto-configure every detected AI client (Claude, Gemini, Cursor, VS Code, …) -------
# Registers the local stdio server in each MCP-capable client found on this machine,
# idempotently and with a per-file backup. Honours the old MTA_SKIP_CLAUDE_SETUP name.
if [ "${MTA_SKIP_SETUP:-${MTA_SKIP_CLAUDE_SETUP:-0}}" != "1" ]; then
  log "Auto-configuring detected AI clients…"
  PATH="$VENV/bin:$PATH" "$PYBIN" -m mta.cli setup 2>&1 | sed 's/^/  /' \
    || log "  (auto-config skipped — run 'mta setup' to do it manually)"
fi

touch "$STATE/installed"
log "Done. Restart Claude (quit + reopen), then say 'Memorise my Documents folder'."
