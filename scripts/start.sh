#!/bin/bash

set -e
cd "$(dirname "$0")/.."

BACKEND_URL="http://localhost:8001"
FRONTEND_URL="http://localhost:5173"
export FRONTEND_DEV_URL="$FRONTEND_URL"

echo "======================================"
echo "   QuantVision Pro starting..."
echo "======================================"

if ! command -v python3 >/dev/null 2>&1; then
  echo "[ERROR] python3 was not found."
  echo "        Install Python 3.10+ first."
  exit 1
fi

if ! command -v node >/dev/null 2>&1; then
  echo "[ERROR] Node.js 18+ was not found."
  echo "        Download: https://nodejs.org/"
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "[ERROR] npm was not found."
  echo "        Reinstall Node.js from: https://nodejs.org/"
  exit 1
fi

if [ ! -d "venv" ]; then
  echo "[INFO] Creating virtual environment..."
  python3 -m venv venv
fi

source venv/bin/activate

echo "[INFO] Installing backend dependencies..."
python3 -m pip install --upgrade pip -q
python3 -m pip install -r backend/requirements.txt -q

echo "[INFO] Installing frontend dependencies..."
(
  cd frontend
  npm install
)

echo
echo "[INFO] Starting frontend service..."
echo "       Frontend: ${FRONTEND_URL}"
(
  cd frontend
  npm run dev -- --host 0.0.0.0 --port 5173
) &
FRONTEND_PID=$!

cleanup() {
  if kill -0 "$FRONTEND_PID" >/dev/null 2>&1; then
    kill "$FRONTEND_PID" >/dev/null 2>&1 || true
  fi
}

trap cleanup EXIT INT TERM

echo
echo "[INFO] Starting backend API..."
echo "       Backend: ${BACKEND_URL}"
echo "       Frontend dev server: ${FRONTEND_URL}"
echo "       API docs: ${BACKEND_URL}/docs"
echo
echo "[INFO] Press Ctrl+C to stop the backend."
echo "======================================"

cd backend
python3 -m uvicorn main:app --host 0.0.0.0 --port 8001 --reload
