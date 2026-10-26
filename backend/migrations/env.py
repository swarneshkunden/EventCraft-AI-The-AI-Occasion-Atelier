"""Alembic migration environment."""
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from app.config.database import Base
from app.config.settings import normalize_database_url
from app.models import models  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _database_url() -> str:
    configured_url = (
        os.environ.get("DATABASE_URL_DIRECT")
        or os.environ.get("DATABASE_URL")
        or config.get_main_option("sqlalchemy.url")
    )
    return normalize_database_url(configured_url)


def run_migrations_offline() -> None:
    database_url = _database_url()
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    database_url = _database_url()
    connect_args = {"connect_timeout": 5} if database_url.startswith("postgresql+psycopg://") else {}
    connectable = create_engine(
        database_url,
        connect_args=connect_args,
        poolclass=pool.NullPool,
        pool_pre_ping=True,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()
    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
