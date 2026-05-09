#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "Building macOS app bundle with PyInstaller..."

python3 -m PyInstaller \
  --noconfirm \
  --clean \
  --windowed \
  --name main \
  --distpath "$PROJECT_ROOT/dist" \
  --workpath "$PROJECT_ROOT/build" \
  --paths "$PROJECT_ROOT" \
  "$SCRIPT_DIR/main.py"

echo
echo "Build complete."
echo "Output: dist/main.app"
