"""
Central error handler – returns generic messages to clients,
logs full detail server-side.
"""
import logging
import traceback

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger(__name__)


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "n/a")


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    log.info(
        "Validation error on %s %s (%d issues)",
        request.method,
        request.url.path,
        len(exc.errors()),
    )
    return JSONResponse(
        status_code=400,
        content={
            "detail": "Invalid request",
            "request_id": _request_id(request),
        },
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    log.info(
        "HTTP error on %s %s (status %d)",
        request.method,
        request.url.path,
        exc.status_code,
    )
    detail = "Authentication required" if exc.status_code == 401 else "Request could not be completed"
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": detail, "request_id": _request_id(request)},
        headers=exc.headers,
    )


async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    log.error(
        "Database error on %s %s [%s] (%s)",
        request.method,
        request.url.path,
        _request_id(request),
        type(exc).__name__,
    )
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Something went wrong",
            "request_id": _request_id(request),
        },
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    log.error(
        "Unhandled exception on %s %s [%s] (%s):\n%s",
        request.method,
        request.url.path,
        _request_id(request),
        type(exc).__name__,
        traceback.format_exc(),
    )
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Something went wrong",
            "request_id": _request_id(request),
        },
    )
