#!/bin/bash
set -e

echo "=== SF Scanner Setup ==="

# Backend
echo ""
echo "[1/3] Installing Python dependencies..."
cd backend
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
pip install -q -r requirements.txt

if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "⚠️  Created backend/.env from template. Open http://localhost:5173 to complete setup (dev) or use launch.command."
fi
cd ..

echo "[2/3] Starting FastAPI backend on http://localhost:8080..."
uvicorn backend.main:app --host 0.0.0.0 --port 8080 --reload &
BACKEND_PID=$!

# Frontend
echo "[3/3] Installing frontend dependencies and starting dev server..."
cd frontend
if [ ! -d "node_modules" ]; then
  npm install
fi
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "✅ SF Scanner is running!"
echo "   Frontend: http://localhost:5173"
echo "   Backend:  http://localhost:8080"
echo "   API Docs: http://localhost:8080/docs"
echo ""
echo "Press Ctrl+C to stop both servers."

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT
wait
