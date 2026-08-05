#!/bin/bash
set -e

SCRIPT_DIR="$(dirname "$0")"

cleanup() {
  echo ""
  echo "Shutting down..."
  kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
  wait $BACKEND_PID $FRONTEND_PID 2>/dev/null
  echo "Done."
}

trap cleanup EXIT INT TERM

echo "=================================="
echo " Dota 2 AI Analyzer - Dev Mode"
echo "=================================="
echo ""
echo " Backend:  http://localhost:8000"
echo " Frontend: http://localhost:5173"
echo ""
echo " Press Ctrl+C to stop"
echo "=================================="
echo ""

# Start backend
(cd "$SCRIPT_DIR/backend" && . venv/bin/activate && uvicorn main:app --reload --host 0.0.0.0 --port 8000) &
BACKEND_PID=$!

# Start frontend
(cd "$SCRIPT_DIR/frontend" && npx vite --host 0.0.0.0 --port 5173) &
FRONTEND_PID=$!

wait
