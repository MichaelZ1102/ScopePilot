# =============================================================================
# ScopePilot — Multi-stage Dockerfile
# =============================================================================

# ── Stage 1: Build frontend ───────────────────────────────────────────────
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

# ── Stage 2: Build Python backend ─────────────────────────────────────────
FROM python:3.11-slim AS backend

WORKDIR /app

# Install system deps for bcrypt + cryptography
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libffi-dev && \
    rm -rf /var/lib/apt/lists/*

# Copy CLI package first (editable dependency)
COPY src/scopepilot/ ./src/scopepilot/
COPY pyproject.toml ./

# Copy backend
COPY backend/pyproject.toml ./backend/
COPY backend/app/ ./backend/app/

# Install dependencies
RUN pip install --no-cache-dir -e . && \
    pip install --no-cache-dir -r backend/requirements.txt 2>/dev/null || \
    pip install --no-cache-dir ./backend

# Copy built frontend from Stage 1
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# ── Runtime ──────────────────────────────────────────────────────────────
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import http.client; c=http.client.HTTPConnection('localhost',8000); c.request('GET','/health'); r=c.getresponse(); exit(0 if r.status==200 else 1)"

# Run with uvicorn
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
