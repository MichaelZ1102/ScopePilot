#!/usr/bin/env bash
# Usage: ./scripts/dev/start.sh [dev|prod]

set -e

MODE="${1:-prod}"
ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"

if [ -x "$BACKEND_DIR/.venv/bin/python" ]; then
    BACKEND_PYTHON="$BACKEND_DIR/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    BACKEND_PYTHON="$(command -v python3)"
else
    BACKEND_PYTHON="$(command -v python)"
fi

check_backend() {
    if ! (cd "$BACKEND_DIR" && "$BACKEND_PYTHON" -c "import app.main") >/dev/null 2>&1; then
        echo "Backend environment is not ready."
        echo "Run: uv sync --project backend"
        echo "Or create backend/.venv and run: backend/.venv/bin/python -m pip install -e . -e backend"
        echo "Also ensure backend/.env or root .env contains SECRET_KEY."
        exit 1
    fi
}

start_backend() {
    echo "Starting backend..."
    cd "$BACKEND_DIR"
    if [ "$MODE" = "dev" ]; then
        "$BACKEND_PYTHON" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
    else
        "$BACKEND_PYTHON" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 &
    fi
    BACKEND_PID=$!
    echo "Backend running on http://localhost:8000 (PID: $BACKEND_PID)"
}

start_frontend() {
    echo "Starting frontend development server..."
    cd "$ROOT_DIR/frontend"
    npm run dev &
    FRONTEND_PID=$!
    echo "Frontend running on http://localhost:5173 (PID: $FRONTEND_PID)"
}

check_backend

if [ "$MODE" = "dev" ]; then
    start_backend
    start_frontend
    echo "Frontend: http://localhost:5173"
    echo "API:      http://localhost:8000/api/v1"
    echo "Health:   http://localhost:8000/health"
    echo "Press Ctrl+C to stop all services"
    trap 'kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true' INT TERM EXIT
    wait
elif [ "$MODE" = "prod" ]; then
    echo "Building frontend..."
    (cd "$ROOT_DIR/frontend" && npm run build)
    start_backend
    echo "Application: http://localhost:8000"
    wait "$BACKEND_PID"
else
    echo "Usage: ./scripts/dev/start.sh [dev|prod]"
    exit 1
fi
