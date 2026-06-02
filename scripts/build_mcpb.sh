#!/usr/bin/env bash
# Build the Claude Desktop bundle: dist/memorised-them-all.mcpb
# Uses the official `mcpb` packer when available (validates the manifest); falls
# back to a spec-compliant zip honouring .mcpbignore. The bundle is source-only —
# launch.sh bootstraps the virtualenv on first run, so no platform-specific venv
# is shipped.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR"
mkdir -p dist
OUT="dist/memorised-them-all.mcpb"
rm -f "$OUT"

if command -v npx >/dev/null 2>&1 && npx -y @anthropic-ai/mcpb --help >/dev/null 2>&1; then
  echo "[mcpb] packing with @anthropic-ai/mcpb"
  npx -y @anthropic-ai/mcpb pack . "$OUT"
else
  echo "[mcpb] mcpb CLI unavailable — building zip from .mcpbignore"
  EXCLUDES=()
  while IFS= read -r line; do
    [ -z "$line" ] && continue
    case "$line" in \#*) continue;; esac
    EXCLUDES+=("-x" "${line%/}/*" "-x" "$line")
  done < .mcpbignore
  # Zip the whole tree MINUS .mcpbignore patterns — same content set the official
  # `mcpb pack` produces, so the two build paths stay in parity (PKG-04).
  zip -r -q "$OUT" . "${EXCLUDES[@]}"
fi

echo "[mcpb] built $OUT ($(wc -c < "$OUT") bytes)"
