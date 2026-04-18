#!/usr/bin/env bash
set -euo pipefail

echo "Building macOS app bundle with PyInstaller..."

python3 -m PyInstaller \
  --noconfirm \
  --clean \
  --windowed \
  --name main \
  main.py

echo
echo "Build complete."
echo "Output: dist/main.app"
