#!/usr/bin/env bash
# Memorised them All — idempotent installer.
# Installs every dependency: Homebrew apps (Ollama, Tesseract, ffmpeg, igraph),
# a Python venv with the latest MarkItDown from upstream, and the local models.
# Safe to re-run; only does work that is actually missing. Apple-silicon first,
# but degrades cleanly on Intel/Linux.
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

# Always pull the LATEST MarkItDown straight from upstream (requirement #1).
log "Installing latest MarkItDown from microsoft/markitdown…"
"$PYBIN" -m pip install --quiet -U \
  "markitdown[pdf,docx,pptx,xlsx,xls,outlook] @ git+https://github.com/microsoft/markitdown.git#subdirectory=packages/markitdown" \
  || log "Upstream MarkItDown install failed; PyPI MarkItDown remains in use."

# Optional accelerators (best-effort; engine falls back if they fail to build).
if [ "$(uname -m)" = "arm64" ] && [ "$(uname -s)" = "Darwin" ]; then
  "$PYBIN" -m pip install --quiet "mlx-whisper>=0.4" >/dev/null 2>&1 \
    && log "Enabled GPU Whisper via Apple MLX." || true
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
  for app in ollama tesseract ffmpeg; do
    command -v "$app" >/dev/null 2>&1 || { log "brew install $app"; brew install "$app" || true; }
  done
  # Many OCR languages (incl. Bengali) + igraph C lib for python-igraph.
  brew list tesseract-lang >/dev/null 2>&1 || brew install tesseract-lang >/dev/null 2>&1 || true
elif command -v apt-get >/dev/null 2>&1 && [ -n "$SUDO$( [ "$(id -u)" = 0 ] && echo root )" ]; then
  log "Installing system apps via apt…"
  $SUDO apt-get update -y >/dev/null 2>&1 || true
  $SUDO apt-get install -y tesseract-ocr tesseract-ocr-all ffmpeg >/dev/null 2>&1 || true
  command -v ollama >/dev/null 2>&1 || curl -fsSL https://ollama.com/install.sh | sh >/dev/null 2>&1 || true
elif command -v dnf >/dev/null 2>&1 && [ -n "$SUDO$( [ "$(id -u)" = 0 ] && echo root )" ]; then
  log "Installing system apps via dnf…"
  $SUDO dnf install -y tesseract ffmpeg >/dev/null 2>&1 || true
  command -v ollama >/dev/null 2>&1 || curl -fsSL https://ollama.com/install.sh | sh >/dev/null 2>&1 || true
elif command -v pacman >/dev/null 2>&1 && [ -n "$SUDO$( [ "$(id -u)" = 0 ] && echo root )" ]; then
  log "Installing system apps via pacman…"
  $SUDO pacman -S --noconfirm tesseract tesseract-data-eng ffmpeg ollama >/dev/null 2>&1 || true
else
  log "No usable package manager (or sudo unavailable) — install Ollama/Tesseract/ffmpeg manually for full features."
fi

# --- 4. Local models (background unless MTA_SKIP_MODELS=1) ------------------
if [ "${MTA_SKIP_MODELS:-0}" != "1" ] && command -v ollama >/dev/null 2>&1; then
  EXTRACT="${MTA_EXTRACT_MODEL:-qwen2.5:7b}"
  EMBED="${MTA_EMBED_MODEL:-nomic-embed-text}"
  VISION="${MTA_VISION_MODEL:-moondream}"
  log "Pulling local models ($EXTRACT, $EMBED, $VISION)…"
  ( ollama serve >/dev/null 2>&1 & sleep 2
    for m in "$EXTRACT" "$EMBED" "$VISION"; do ollama pull "$m" >/dev/null 2>&1 || true; done
  ) &
fi

touch "$STATE/installed"
log "Done. Run 'mta status' to verify, or 'mta digest <folder>' to begin."
