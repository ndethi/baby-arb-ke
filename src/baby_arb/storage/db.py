"""SQLModel engine and sessions for the one project database.

SQLite connections get foreign keys enforced and WAL journaling, so the bot
process and cron-run CLI commands can use the database at the same time.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache
from typing import Any

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlmodel import Session, create_engine

from baby_arb.config import get_settings


def make_engine(url: str) -> Engine:
    """Create an engine for `url`, applying SQLite pragmas when relevant.

    Args:
        url: SQLAlchemy database URL.

    Returns:
        A configured Engine.
    """
    engine = create_engine(url)
    if engine.dialect.name == "sqlite":

        @event.listens_for(engine, "connect")
        def _sqlite_pragmas(dbapi_conn: Any, _record: Any) -> None:
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()

    return engine


@lru_cache(maxsize=4)
def get_engine(url: str | None = None) -> Engine:
    """Return a cached engine for `url` (default: settings.database_url)."""
    return make_engine(url or get_settings().database_url)


@contextmanager
def session_scope(engine: Engine | None = None) -> Iterator[Session]:
    """Yield a session that commits on success and rolls back on error.

    Args:
        engine: Engine to use; defaults to the configured database.
    """
    with Session(engine or get_engine()) as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
