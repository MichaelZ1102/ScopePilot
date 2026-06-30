#!/usr/bin/env bash
# ScopePilot 一键启动脚本
# 用法: ./scripts/start.sh [dev|prod]

set -e

MODE="${1:-prod}"
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "🚀 ScopePilot - $MODE mode"

start_backend() {
    echo "📦 Starting backend..."
    cd "$ROOT_DIR/backend"
    
    # Check for .env
    if [ ! -f .env ]; then
        if [ -f .env.example ]; then
            cp .env.example .env
            echo "⚠️  Created .env from .env.example — please edit it with your keys"
        fi
    fi
    
    python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
    BACKEND_PID=$!
    echo "✅ Backend running on http://localhost:8000 (PID: $BACKEND_PID)"
}

start_frontend() {
    echo "🎨 Starting frontend dev server..."
    cd "$ROOT_DIR/frontend"
    npm run dev &
    FRONTEND_PID=$!
    echo "✅ Frontend running on http://localhost:5173 (PID: $FRONTEND_PID)"
}

if [ "$MODE" = "dev" ]; then
    start_backend
    start_frontend
    echo ""
    echo "📋 访问地址:"
    echo "   Frontend: http://localhost:5173"
    echo "   API:      http://localhost:8000/api/v1"
    echo "   Health:   http://localhost:8000/health"
    echo ""
    echo "Press Ctrl+C to stop all services"
    trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
    wait
else
    start_backend
    echo ""
    echo "📋 访问地址: http://localhost:8000"
    echo "   (Frontend 由 FastAPI 直接 serve dist/)"
    echo ""
    wait $BACKEND_PID
fi
