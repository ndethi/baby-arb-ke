"""Alembic environment for the project database.

URL: `sqlalchemy.url` if a caller set it (tests, `baby-arb db upgrade --url`),
otherwise DATABASE_URL from settings. SQLite needs batch mode for ALTER TABLE.
"""

from __future__ import annotations

import baby_arb.posting.tables  # noqa: F401  (registers tables on the metadata)
from alembic import context
from baby_arb.config import get_settings
from baby_arb.storage.db import make_engine
from sqlmodel import SQLModel

config = context.config
target_metadata = SQLModel.metadata


def _url() -> str:
    return config.get_main_option("sqlalchemy.url") or get_settings().database_url


def run_migrations_offline() -> None:
    """Emit SQL to stdout without a database connection."""
    context.configure(
        url=_url(), target_metadata=target_metadata, literal_binds=True, render_as_batch=True
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against the database."""
    engine = make_engine(_url())
    with engine.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata, render_as_batch=True
        )
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
