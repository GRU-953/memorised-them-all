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
  zip -r -q "$OUT" \
    manifest.json launch.sh install.sh requirements.txt pyproject.toml \
    README.md LICENSE CHANGELOG.md ACKNOWLEDGEMENTS.md \
    mta templates assets "${EXCLUDES[@]}"
fi

echo "[mcpb] built $OUT ($(wc -c < "$OUT") bytes)"
