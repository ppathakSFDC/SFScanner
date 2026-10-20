#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Install uv if missing (fast Python package manager, no admin required)
if ! command -v uv &>/dev/null; then
    echo "Installing uv (first run only)..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi
export PATH="$HOME/.local/bin:$PATH"

PORT=8080

if lsof -iTCP:$PORT -sTCP:LISTEN >/dev/null 2>&1; then
    echo "Port $PORT is already in use. Close the existing process and try again."
    exit 1
fi

# Create Python virtual environment
if [ ! -d "backend/.venv" ]; then
    echo "Creating Python environment (first run only)..."
    uv venv --python 3.11 backend/.venv
fi

echo "Syncing Python dependencies..."
uv pip install -q -r backend/requirements.txt --python backend/.venv/bin/python

# Rebuild frontend bundle when sources are newer than the current build
if [ -d "frontend/src" ] && command -v npm &>/dev/null; then
    NEEDS_BUILD=0
    if [ ! -f "frontend/dist/index.html" ]; then
        NEEDS_BUILD=1
    else
        if [ -n "$(find frontend/src frontend/index.html frontend/package.json frontend/vite.config.js -newer frontend/dist/index.html 2>/dev/null | head -n 1)" ]; then
            NEEDS_BUILD=1
        fi
    fi
    if [ "$NEEDS_BUILD" = "1" ]; then
        echo "Building frontend bundle..."
        if [ ! -d "frontend/node_modules" ]; then
            (cd frontend && npm install --silent)
        fi
        (cd frontend && npm run build --silent)
    fi
fi

echo ""
echo "  SF Scanner — Salesforce Best Practice Analyzer"
echo "  App URL: http://localhost:$PORT"
echo ""

backend/.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port $PORT &
UVICORN_PID=$!

cleanup() {
    kill $UVICORN_PID 2>/dev/null || true
}
trap cleanup EXIT

(sleep 2 && open "http://localhost:$PORT" >/dev/null 2>&1 || true) &

wait $UVICORN_PID
