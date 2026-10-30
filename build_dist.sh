#!/usr/bin/env bash
# Build SF Scanner into a single self-contained executable
# Output: dist/sfscanner  (macOS/Linux) or dist/sfscanner.exe (Windows)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "=== [1/3] Building React frontend ==="
cd "$ROOT/frontend"
npm ci --silent
npm run build
echo "Frontend built → frontend/dist/"

echo ""
echo "=== [2/3] Installing PyInstaller ==="
cd "$ROOT/backend"
# Install into the venv if it exists, otherwise system Python
if [ -f ".venv/bin/pip" ]; then
  .venv/bin/pip install --quiet pyinstaller
  PYINSTALLER=".venv/bin/pyinstaller"
else
  pip install --quiet pyinstaller
  PYINSTALLER="pyinstaller"
fi

echo ""
echo "=== [3/3] Running PyInstaller ==="
cd "$ROOT"
$PYINSTALLER sfscanner.spec --noconfirm --clean

echo ""
echo "====================================================="
echo "Build complete!  Executable → dist/sfscanner"
echo ""
echo "To run:"
echo "  ./dist/sfscanner"
echo ""
echo "Users need to create a .env file next to the executable:"
echo "  SF_CLIENT_ID=..."
echo "  SF_CLIENT_SECRET=..."
echo "  ANTHROPIC_API_KEY=..."
echo "  SESSION_SECRET=some-random-string"
echo "====================================================="
