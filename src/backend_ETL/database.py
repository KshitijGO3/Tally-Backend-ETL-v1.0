"""SQLAlchemy engine and session factory helpers."""

from __future__ import annotations

from typing import Any

import psycopg
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool


def make_engine(dsn: str, use_pool: bool = True) -> Engine:
    """Builds a SQLAlchemy engine on the psycopg (v3) driver from a libpq DSN."""
    pool_args: dict[str, Any] = (
        {"pool_size": 10, "max_overflow": 0, "pool_pre_ping": True}
        if use_pool
        else {"poolclass": NullPool}
    )
    if "://" in dsn:
        url = dsn.replace("postgresql://", "postgresql+psycopg://", 1)
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
        return create_engine(url, **pool_args)
    # keyword-style DSN ("host=... dbname=...")
    return create_engine("postgresql+psycopg://", creator=lambda: psycopg.connect(dsn), **pool_args)


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Sessions keep returned objects usable after commit (expire_on_commit=False)."""
    return sessionmaker(engine, expire_on_commit=False)
