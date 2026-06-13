"""Alembic environment for FundSmart triage service tables."""

from __future__ import annotations

import os
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool, text

from services.triage_service.models import Base, TRIAGE_SCHEMA

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env", override=False)
load_dotenv(REPO_ROOT / "services" / "triage_service" / ".env", override=False)

target_metadata = Base.metadata


def database_url_from_env() -> str:
    database_url = (
        os.getenv("DEFAULT_DATABASE_URL")
        or os.getenv("TRIAGE_DATABASE_URL")
        or os.getenv("DATABASE_URL")
    )
    if not database_url:
        raise RuntimeError(
            "Set DEFAULT_DATABASE_URL, TRIAGE_DATABASE_URL, or DATABASE_URL for Alembic."
        )
    return normalize_database_url(database_url)


def normalize_database_url(database_url: str) -> str:
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return database_url


def run_migrations_offline() -> None:
    context.configure(
        url=database_url_from_env(),
        target_metadata=target_metadata,
        include_schemas=True,
        version_table_schema=TRIAGE_SCHEMA,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.execute(f"CREATE SCHEMA IF NOT EXISTS {TRIAGE_SCHEMA}")
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = database_url_from_env()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {TRIAGE_SCHEMA}"))
        connection.commit()
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            version_table_schema=TRIAGE_SCHEMA,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
