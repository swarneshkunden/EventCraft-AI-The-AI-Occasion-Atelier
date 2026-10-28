"""
Application configuration loaded from environment variables.
All security-sensitive defaults are deliberately absent – they must be set in .env.
"""
from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import parse_qs, urlsplit

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[3] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── App ──────────────────────────────────────────────────────────────
    APP_ENV: Literal["development", "production", "test"] = "development"
    APP_SECRET_KEY: str
    CURRENCY: str = "INR"
    ALLOWED_ORIGINS: str = "http://localhost:8000,http://127.0.0.1:8000"  # comma-separated

    # ── Database ─────────────────────────────────────────────────────────
    DATABASE_URL: str = "sqlite:///./eventplanner.db"
    DATABASE_URL_DIRECT: str | None = None
    DB_POOL_SIZE: int = Field(default=3, ge=1, le=5)
    DB_MAX_OVERFLOW: int = Field(default=0, ge=0, le=5)
    DB_POOL_RECYCLE_SECONDS: int = Field(default=300, ge=60, le=3600)
    DB_POOL_TIMEOUT_SECONDS: int = Field(default=10, ge=1, le=60)
    DB_CONNECT_TIMEOUT_SECONDS: int = Field(default=5, ge=1, le=30)
    DB_CONNECT_RETRIES: int = Field(default=3, ge=1, le=5)
    DB_RETRY_BACKOFF_SECONDS: float = Field(default=0.5, gt=0, le=5)

    # ── Auth / JWT ────────────────────────────────────────────────────────
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    JWT_ALGORITHM: str = "HS256"

    # ── Gemini ────────────────────────────────────────────────────────────
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.8-flash"
    GEMINI_TIMEOUT_SECONDS: int = 30
    GEMINI_MAX_RETRIES: int = 3
    GEMINI_RETRY_BACKOFF_BASE: float = 1.5
    AI_CACHE_TTL_SECONDS: int = Field(default=3600, gt=0)
    AI_CACHE_MAX_ENTRIES: int = Field(default=256, gt=0)

    # ── Rate limiting ─────────────────────────────────────────────────────
    # Auth routes
    RATE_AUTH_WINDOW_SECONDS: int = Field(default=300, gt=0, le=300)
    RATE_AUTH_MAX_REQUESTS: int = 10
    RATE_AUTH_ACCOUNT_WINDOW_SECONDS: int = Field(default=300, gt=0, le=300)
    RATE_AUTH_ACCOUNT_MAX_REQUESTS: int = 10
    # Authenticated user actions
    RATE_USER_WINDOW_SECONDS: int = 60
    RATE_USER_MAX_REQUESTS: int = 120
    # AI endpoints
    RATE_AI_WINDOW_SECONDS: int = 60
    RATE_AI_MAX_REQUESTS: int = 20
    RATE_AI_DAILY_WINDOW_SECONDS: int = 86400
    RATE_AI_DAILY_MAX_REQUESTS: int = 200
    # Exponential backoff for failed auth
    RATE_AUTH_BACKOFF_BASE: float = 2.0
    RATE_AUTH_BACKOFF_CAP_SECONDS: float = 300.0
    RATE_MAX_TRACKED_KEYS: int = Field(default=50000, gt=0)

    # ── File uploads ──────────────────────────────────────────────────────
    UPLOAD_MAX_BYTES: int = 2 * 1024 * 1024  # 2 MB
    UPLOAD_MAX_ROWS: int = 500
    UPLOAD_DIR: str = "uploads"  # outside web root

    # ── Misc ──────────────────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"
    BODY_MAX_BYTES: int = 1 * 1024 * 1024  # 1 MB

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def _strip_origins(cls, v: str) -> str:
        return v.strip()

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def _normalize_database_url(cls, value: str) -> str:
        return normalize_database_url(value)

    @field_validator("DATABASE_URL_DIRECT", mode="before")
    @classmethod
    def _normalize_direct_database_url(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        return normalize_database_url(value)

    @field_validator("GEMINI_MODEL", mode="before")
    @classmethod
    def _replace_shutdown_gemini_models(cls, value: str) -> str:
        retired_models = {
            "gemini-2.0-flash",
            "gemini-2.0-flash-001",
        }
        model = value.strip()
        if model in retired_models:
            return "gemini-3.8-flash"
        return model

    def allowed_origins_list(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    @model_validator(mode="after")
    def _require_signing_secret(self) -> "Settings":
        secret = self.APP_SECRET_KEY.strip()
        if len(secret) < 32:
            raise ValueError("APP_SECRET_KEY must be at least 32 characters")
        if secret != self.APP_SECRET_KEY:
            raise ValueError("APP_SECRET_KEY must not contain leading or trailing whitespace")
        for database_url in (self.DATABASE_URL, self.DATABASE_URL_DIRECT):
            if database_url:
                hostname = urlsplit(database_url).hostname or ""
                if hostname.endswith(".neon.tech"):
                    query = parse_qs(urlsplit(database_url).query)
                    if query.get("sslmode") != ["require"]:
                        raise ValueError("Neon database URLs must require SSL with sslmode=require")
        if self.APP_ENV == "production":
            if secret.lower().startswith(("replace-", "changeme", "your-", "example-")):
                raise ValueError("Production requires a newly generated APP_SECRET_KEY")
            if not self.DATABASE_URL.startswith("postgresql+psycopg://"):
                raise ValueError(
                    "Production requires a durable PostgreSQL database using the psycopg driver"
                )
            database_host = urlsplit(self.DATABASE_URL).hostname or ""
            if database_host.endswith(".neon.tech") and "pooler" not in database_host:
                raise ValueError("Production Neon DATABASE_URL must use the pooled hostname")
            for origin in self.allowed_origins_list():
                parsed = urlsplit(origin)
                if (
                    parsed.scheme != "https"
                    or not parsed.hostname
                    or parsed.username
                    or parsed.password
                    or parsed.path
                    or parsed.query
                    or parsed.fragment
                    or "*" in parsed.netloc
                ):
                    raise ValueError(
                        "Production ALLOWED_ORIGINS entries must be HTTPS origins without paths"
                    )
        return self


def normalize_database_url(value: str) -> str:
    """Select psycopg 3 for PostgreSQL URLs while preserving query parameters."""
    url = value.strip()
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    return url


@lru_cache
def get_settings() -> Settings:
    return Settings()
