#!/usr/bin/env bash
# Build Tailwind CSS for the Necker web UI.
#
# Prerequisites:
#   Download the standalone Tailwind CLI binary (v3.4.17) from:
#   https://github.com/tailwindlabs/tailwindcss/releases/download/v3.4.17/tailwindcss-linux-x64
#   Place it at /usr/local/bin/tailwindcss (or anywhere on PATH) and chmod +x.
#
# Usage:
#   ./scripts/build-css.sh           # one-shot build (minified)
#   ./scripts/build-css.sh --watch   # watch mode for development

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

INPUT="$REPO_ROOT/app/static/src/input.css"
OUTPUT="$REPO_ROOT/app/static/dist/app.css"
CONFIG="$REPO_ROOT/tailwind.config.js"

if ! command -v tailwindcss &>/dev/null; then
  echo "Error: tailwindcss binary not found on PATH." >&2
  echo "Download v3.4.17 from:" >&2
  echo "  https://github.com/tailwindlabs/tailwindcss/releases/download/v3.4.17/tailwindcss-linux-x64" >&2
  echo "Place it at /usr/local/bin/tailwindcss and chmod +x." >&2
  exit 1
fi

mkdir -p "$(dirname "$OUTPUT")"

if [[ "${1:-}" == "--watch" ]]; then
  exec tailwindcss -c "$CONFIG" -i "$INPUT" -o "$OUTPUT" --watch
else
  exec tailwindcss -c "$CONFIG" -i "$INPUT" -o "$OUTPUT" --minify
fi
