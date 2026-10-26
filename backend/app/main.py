"""
FastAPI application entry point.
Wires together all routers, middleware, and static file serving.
"""
import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi import HTTPException
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text

from app.config import configure_logging, engine, get_settings
from app.middleware import (
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
    generic_exception_handler,
    http_exception_handler,
    sqlalchemy_exception_handler,
    validation_exception_handler,
)
from app.routes import (
    auth_router,
    budget_router,
    chat_router,
    demo_router,
    events_router,
    guests_router,
    plan_health_router,
    tasks_router,
    vendors_router,
)

configure_logging()
log = logging.getLogger(__name__)
settings = get_settings()

app = FastAPI(
    title="Event Planner API",
    version="1.0.0",
    docs_url="/api/docs" if settings.APP_ENV != "production" else None,
    redoc_url=None,
    openapi_url="/api/openapi.json" if settings.APP_ENV != "production" else None,
)

# ── Middleware (order matters – outermost first) ───────────────────────────────
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    max_age=600,
)

# ── Error handlers ────────────────────────────────────────────────────────────
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(SQLAlchemyError, sqlalchemy_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

# ── API routers ───────────────────────────────────────────────────────────────
for router in [
    auth_router,
    events_router,
    budget_router,
    tasks_router,
    vendors_router,
    guests_router,
    chat_router,
    demo_router,
    plan_health_router,
]:
    app.include_router(router)


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/api/health", tags=["health"])
async def health() -> dict:
    return {"status": "ok"}


@app.get("/healthz", tags=["health"])
async def healthz() -> dict:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        log.error("Database health probe failed (%s)", type(exc).__name__)
        raise HTTPException(status_code=503, detail="Health check unavailable") from exc
    return {"status": "ok"}


_STATIC_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"
if not _STATIC_DIR.exists():
    _STATIC_DIR = Path.cwd() / "frontend"
if not _STATIC_DIR.exists():
    _STATIC_DIR = Path.cwd().parent / "frontend"

if _STATIC_DIR.exists():
    app.mount(
        "/src",
        StaticFiles(directory=str(_STATIC_DIR / "src")),
        name="static-src",
    )
    app.mount(
        "/static",
        StaticFiles(directory=str(_STATIC_DIR / "src" / "styles")),
        name="static-styles",
    )
    app.mount(
        "/js",
        StaticFiles(directory=str(_STATIC_DIR / "src")),
        name="static-js",
    )

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str, request: Request) -> FileResponse:
        """Serve the SPA index for all non-API routes."""
        index = _STATIC_DIR / "index.html"
        return FileResponse(str(index), headers={"Cache-Control": "no-cache"})
