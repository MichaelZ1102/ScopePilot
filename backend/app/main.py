"""FastAPI application entry point."""
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from logging.handlers import RotatingFileHandler
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import ResponseValidationError
from starlette.responses import FileResponse, JSONResponse
from urllib.parse import urlparse

from .config import settings

# ── Logging configuration ─────────────────────────────────────────────────
log_formatter = logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG if settings.debug else logging.INFO)


def _add_handler_once(handler: logging.Handler, name: str) -> None:
    if any(existing.get_name() == name for existing in root_logger.handlers):
        return
    handler.set_name(name)
    root_logger.addHandler(handler)


console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)
_add_handler_once(console_handler, "scopepilot-console")

log_dir = Path(__file__).resolve().parent.parent.parent / "logs"
log_dir.mkdir(exist_ok=True)
file_handler = RotatingFileHandler(
    log_dir / "app.log",
    maxBytes=10 * 1024 * 1024,
    backupCount=5,
    encoding="utf-8",
)
file_handler.setFormatter(log_formatter)
_add_handler_once(file_handler, "scopepilot-file")

# Quiet noisy third-party loggers
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


def _origin_from_url(value: str) -> str:
    parsed = urlparse(value)
    if not parsed.scheme or not parsed.netloc:
        return ""
    return f"{parsed.scheme}://{parsed.netloc}"


def _allowed_request_origin(request: Request) -> bool:
    origin = request.headers.get("origin")
    referer = request.headers.get("referer")
    candidate = origin or _origin_from_url(referer or "")
    if not candidate:
        return True

    host = request.headers.get("host", "")
    same_origin = f"{request.url.scheme}://{host}" if host else ""
    allowed_origins = set(settings.cors_origins)
    if same_origin:
        allowed_origins.add(same_origin)
    return candidate in allowed_origins

from .api.v1 import auth, projects, sprints, reports, tickets, analysis, codebase, api_tests, figma, team, notifications
from .startup import load_persisted_data


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_persisted_data()
    yield


app = FastAPI(
    title="ScopePilot",
    version="0.6.0",
    description="AI-powered Sprint Requirement Analysis Platform",
    lifespan=lifespan,
)

# CORS - allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def csrf_origin_guard(request: Request, call_next):
    if request.url.path.startswith("/api/") and request.method not in {"GET", "HEAD", "OPTIONS"}:
        if not _allowed_request_origin(request):
            return JSONResponse(status_code=403, content={"detail": "Invalid request origin"})
    return await call_next(request)


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
app.include_router(notifications.router, prefix="/api/v1/notifications", tags=["notifications"])

# Serve frontend static files in production
frontend_dist = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    frontend_assets = frontend_dist / "assets"
    if frontend_assets.exists():
        app.mount(
            "/assets",
            StaticFiles(directory=str(frontend_assets)),
            name="frontend-assets",
        )

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_frontend(full_path: str):
        """Serve built files and fall back to index.html for client-side routes."""
        if full_path == "api" or full_path.startswith("api/"):
            return JSONResponse(status_code=404, content={"detail": "Not Found"})

        dist_root = frontend_dist.resolve()
        requested_file = (dist_root / full_path).resolve()
        if requested_file.is_file() and dist_root in requested_file.parents:
            return FileResponse(requested_file)
        return FileResponse(dist_root / "index.html")

    logger.info("Serving frontend from %s", frontend_dist)
else:
    logger.info("Frontend dist not found at %s; API only mode", frontend_dist)
