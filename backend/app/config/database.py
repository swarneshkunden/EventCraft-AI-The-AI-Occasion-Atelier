"""Database setup using SQLAlchemy with SQLite."""
import logging
import time
from collections.abc import Generator
from contextlib import contextmanager

from psycopg import OperationalError as PsycopgOperationalError
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config.settings import get_settings

log = logging.getLogger(__name__)

settings = get_settings()

is_sqlite = settings.DATABASE_URL.startswith("sqlite")
is_postgresql = settings.DATABASE_URL.startswith("postgresql+psycopg://")
connect_args = (
    {"check_same_thread": False, "timeout": settings.DB_CONNECT_TIMEOUT_SECONDS}
    if is_sqlite
    else {"connect_timeout": settings.DB_CONNECT_TIMEOUT_SECONDS}
    if is_postgresql
    else {}
)
engine_options = {
    "connect_args": connect_args,
    "echo": settings.APP_ENV == "development",
    "pool_pre_ping": True,
}
if is_postgresql:
    engine_options.update(
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_recycle=settings.DB_POOL_RECYCLE_SECONDS,
        pool_timeout=settings.DB_POOL_TIMEOUT_SECONDS,
    )

engine = create_engine(settings.DATABASE_URL, **engine_options)


if is_postgresql:
    @event.listens_for(engine, "do_connect")
    def _connect_with_retry(dialect, _connection_record, cargs, cparams):
        for attempt in range(settings.DB_CONNECT_RETRIES):
            try:
                return dialect.connect(*cargs, **cparams)
            except PsycopgOperationalError as exc:
                if attempt + 1 == settings.DB_CONNECT_RETRIES:
                    log.error("Database connection failed (%s)", type(exc).__name__)
                    raise
                delay = settings.DB_RETRY_BACKOFF_SECONDS * (2 ** attempt)
                log.warning(
                    "Database connection attempt %d/%d failed (%s); retrying in %.1fs",
                    attempt + 1,
                    settings.DB_CONNECT_RETRIES,
                    type(exc).__name__,
                    delay,
                )
                time.sleep(delay)


if settings.DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that provides a DB session per request."""
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@contextmanager
def db_session() -> Generator[Session, None, None]:
    """Context-manager version for use outside of FastAPI dependency injection."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
