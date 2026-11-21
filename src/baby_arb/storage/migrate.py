"""Run Alembic migrations from code (CLI, tests)."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config

REPO_ROOT = Path(__file__).resolve().parents[3]


def alembic_config(url: str | None = None) -> Config:
    """Alembic config for this repo; `url` overrides DATABASE_URL."""
    cfg = Config(str(REPO_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(REPO_ROOT / "migrations"))
    if url:
        cfg.set_main_option("sqlalchemy.url", url)
    return cfg


def run_migrations(url: str | None = None, revision: str = "head") -> None:
    """Upgrade the database to `revision`."""
    command.upgrade(alembic_config(url), revision)


def downgrade(url: str | None, revision: str) -> None:
    """Downgrade the database to `revision` (tests and recovery only)."""
    command.downgrade(alembic_config(url), revision)
