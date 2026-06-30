"""FastAPI application entry point."""
import logging
import os
from pathlib import Path
from logging.handlers import RotatingFileHandler
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import ResponseValidationError
from starlette.responses import JSONResponse, FileResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .config import settings

# ── Logging configuration ─────────────────────────────────────────────────
log_formatter = logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG if settings.debug else logging.INFO)

console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)
root_logger.addHandler(console_handler)

log_dir = Path(__file__).resolve().parent.parent.parent / "logs"
log_dir.mkdir(exist_ok=True)
file_handler = RotatingFileHandler(
    log_dir / "app.log",
    maxBytes=10 * 1024 * 1024,
    backupCount=5,
    encoding="utf-8",
)
file_handler.setFormatter(log_formatter)
root_logger.addHandler(file_handler)

# Quiet noisy third-party loggers
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

from .api.v1 import auth, projects, sprints, reports, tickets, analysis, codebase, api_tests, figma, team
from .startup import load_persisted_data

app = FastAPI(
    title="ScopePilot",
    version="0.5.0",
    description="AI-powered Sprint Requirement Analysis Platform",
)

# CORS - allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ResponseValidationError)
async def validation_exception_handler(request: Request, exc: ResponseValidationError):
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "body": exc.body},
    )


@app.get("/health")
async def health():
    return {"status": "ok"}


# Mount API routers (before static files so /api/* takes priority)
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(projects.router, prefix="/api/v1/projects", tags=["projects"])
app.include_router(sprints.router, prefix="/api/v1/sprints", tags=["sprints"])
app.include_router(tickets.router, prefix="/api/v1/tickets", tags=["tickets"])
app.include_router(reports.router, prefix="/api/v1/reports", tags=["reports"])
app.include_router(analysis.router, prefix="/api/v1/analysis", tags=["analysis"])
app.include_router(codebase.router, prefix="/api/v1/code-sources", tags=["codebase"])
app.include_router(api_tests.router, prefix="/api/v1/api-tests", tags=["api-tests"])
app.include_router(figma.router, prefix="/api/v1/figma", tags=["figma"])
app.include_router(team.router, prefix="/api/v1/team", tags=["team"])

# Serve frontend static files in production
frontend_dist = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")
    print(f"✅ Serving frontend from {frontend_dist}")
else:
    print(f"ℹ️  Frontend dist not found at {frontend_dist} — API only mode")

# Load persisted data from disk at startup
load_persisted_data()
