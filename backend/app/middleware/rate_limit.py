"""
In-memory rate limiter using a sliding window counter.
All thresholds are loaded from settings – nothing is hardcoded.
"""
import asyncio
import logging
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass, field

import jwt
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config.settings import get_settings

log = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class _WindowState:
    timestamps: list[float] = field(default_factory=list)
    failure_count: int = 0  # for auth backoff
    last_failure_at: float = 0.0
    last_touched_at: float = 0.0


class _SlidingWindowStore:
    """Async-safe, bounded sliding windows held in this process."""

    def __init__(self) -> None:
        self._store: OrderedDict[str, _WindowState] = OrderedDict()
        self._lock = asyncio.Lock()
        self._operations = 0

    def _get_or_create(self, key: str, now: float) -> _WindowState:
        state = self._store.get(key)
        if state is None:
            state = _WindowState()
            self._store[key] = state
        state.last_touched_at = now
        self._store.move_to_end(key)
        return state

    def _prune(self, now: float) -> None:
        self._operations += 1
        if (
            len(self._store) >= settings.RATE_MAX_TRACKED_KEYS
            and self._operations % 1024 == 0
        ):
            retention = max(
                settings.RATE_AUTH_WINDOW_SECONDS,
                settings.RATE_AUTH_ACCOUNT_WINDOW_SECONDS,
                settings.RATE_USER_WINDOW_SECONDS,
                settings.RATE_AI_DAILY_WINDOW_SECONDS,
            )
            cutoff = now - retention
            expired = [
                key
                for key, state in self._store.items()
                if state.last_touched_at <= cutoff
                and state.last_failure_at <= cutoff
                and not any(timestamp > cutoff for timestamp in state.timestamps)
            ]
            for key in expired:
                del self._store[key]

        while len(self._store) > settings.RATE_MAX_TRACKED_KEYS:
            self._store.popitem(last=False)

    async def is_allowed(
        self,
        key: str,
        window_seconds: int,
        max_requests: int,
    ) -> bool:
        now = time.monotonic()
        cutoff = now - window_seconds

        async with self._lock:
            state = self._get_or_create(key, now)
            state.timestamps = [t for t in state.timestamps if t > cutoff]
            if len(state.timestamps) >= max_requests:
                self._prune(now)
                return False
            state.timestamps.append(now)
            self._prune(now)
            return True

    async def record_auth_failure(self, key: str) -> int:
        """Increment failure counter and return current count."""
        now = time.monotonic()
        async with self._lock:
            state = self._get_or_create(key, now)
            if (
                state.last_failure_at
                and now - state.last_failure_at >= settings.RATE_AUTH_ACCOUNT_WINDOW_SECONDS
            ):
                state.failure_count = 0
            state.failure_count += 1
            state.last_failure_at = now
            self._prune(now)
            return state.failure_count

    async def reset_auth_failures(self, key: str) -> None:
        async with self._lock:
            state = self._store.get(key)
            if state is None:
                return
            state.failure_count = 0
            state.last_failure_at = 0.0
            if not state.timestamps:
                del self._store[key]

    async def get_auth_failure_delay(self, key: str) -> float:
        """Return exponential backoff delay in seconds based on failure count."""
        now = time.monotonic()
        async with self._lock:
            state = self._store.get(key)
            if state is None:
                return 0.0
            if (
                state.last_failure_at
                and now - state.last_failure_at >= settings.RATE_AUTH_ACCOUNT_WINDOW_SECONDS
            ):
                state.failure_count = 0
                state.last_failure_at = 0.0
                if not state.timestamps:
                    del self._store[key]
                return 0.0
            failures = state.failure_count
        if failures == 0:
            return 0.0
        delay = settings.RATE_AUTH_BACKOFF_BASE ** failures
        return min(delay, settings.RATE_AUTH_BACKOFF_CAP_SECONDS)


_store = _SlidingWindowStore()


def get_rate_limit_store() -> _SlidingWindowStore:
    return _store


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Route-aware rate limiter:
    - Login, signup, and token refresh → strict per-IP limits
    - AI endpoints → per-user AI limits
    - Other routes → per-user moderate limits
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path
        ip = self._get_ip(request)

        if request.method == "POST" and path in {
            "/api/auth/login",
            "/api/auth/signup",
            "/api/auth/refresh-cookie",
        }:
            key = f"auth:{ip}"
            allowed = await _store.is_allowed(
                key, settings.RATE_AUTH_WINDOW_SECONDS, settings.RATE_AUTH_MAX_REQUESTS
            )
            if not allowed:
                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": "Too many requests. Please wait before trying again.",
                        "request_id": getattr(request.state, "request_id", "n/a"),
                    },
                    headers={
                        "Retry-After": str(settings.RATE_AUTH_WINDOW_SECONDS),
                        "X-Request-ID": getattr(request.state, "request_id", "n/a"),
                    },
                )

        elif self._is_ai_endpoint(path, request.method):
            user_id = self._get_user_id(request) or ip
            key = f"ai:{user_id}"
            short_window_allowed = await _store.is_allowed(
                key, settings.RATE_AI_WINDOW_SECONDS, settings.RATE_AI_MAX_REQUESTS
            )
            if not short_window_allowed:
                return self._rate_limited(
                    request,
                    "AI rate limit reached. Please wait a moment.",
                    settings.RATE_AI_WINDOW_SECONDS,
                )
            daily_window_allowed = await _store.is_allowed(
                f"{key}:daily",
                settings.RATE_AI_DAILY_WINDOW_SECONDS,
                settings.RATE_AI_DAILY_MAX_REQUESTS,
            )
            if not daily_window_allowed:
                return self._rate_limited(
                    request,
                    "AI rate limit reached. Please wait a moment.",
                    settings.RATE_AI_DAILY_WINDOW_SECONDS,
                )

        else:
            user_id = self._get_user_id(request) or ip
            key = f"user:{user_id}"
            allowed = await _store.is_allowed(
                key, settings.RATE_USER_WINDOW_SECONDS, settings.RATE_USER_MAX_REQUESTS
            )
            if not allowed:
                return self._rate_limited(
                    request,
                    "Too many requests. Please slow down.",
                    settings.RATE_USER_WINDOW_SECONDS,
                )

        return await call_next(request)

    @staticmethod
    def _rate_limited(request: Request, message: str, retry_after: int) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "n/a")
        return JSONResponse(
            status_code=429,
            content={"detail": message, "request_id": request_id},
            headers={"Retry-After": str(retry_after), "X-Request-ID": request_id},
        )

    @staticmethod
    def _get_ip(request: Request) -> str:
        return request.client.host if request.client else "unknown"

    @staticmethod
    def _get_user_id(request: Request) -> str | None:
        authorization = request.headers.get("authorization", "")
        token = (
            authorization[7:]
            if authorization.lower().startswith("bearer ")
            else request.cookies.get("access_token")
        )
        if not token:
            return None
        try:
            payload = jwt.decode(
                token,
                settings.APP_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM],
            )
            user_id = payload.get("sub")
            return user_id if isinstance(user_id, str) else None
        except jwt.PyJWTError:
            return None

    @staticmethod
    def _is_ai_endpoint(path: str, method: str) -> bool:
        if method not in {"POST", "GET"}:
            return False
        return (
            "/budget/ai-split" in path
            or "/budget/scenario" in path
            or path.endswith(("/tasks/generate", "/generate-questions", "/chat/ideas"))
            or (path.endswith("/chat") and method == "POST")
            or ("/plan-health/crisis" in path and method == "POST")
        )
