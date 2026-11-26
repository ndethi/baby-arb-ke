"""Alembic migrations match the models and round-trip."""

from __future__ import annotations

import baby_arb.posting.tables  # noqa: F401
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from baby_arb.storage.db import make_engine
from baby_arb.storage.migrate import downgrade, run_migrations
from sqlalchemy import inspect
from sqlmodel import SQLModel

PHASE0_TABLES = {
    "listings", "photos", "listing_events", "safety_verdicts",
    "llm_calls", "code_counters", "bot_state",
}


def test_head_schema_matches_models(db_url):
    engine = make_engine(db_url)
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), SQLModel.metadata)
    engine.dispose()
    assert diff == []


def test_upgrade_downgrade_upgrade(db_url):
    engine = make_engine(db_url)
    assert set(inspect(engine).get_table_names()) >= PHASE0_TABLES
    downgrade(db_url, "base")
    assert set(inspect(engine).get_table_names()) <= {"alembic_version"}
    run_migrations(db_url)
    assert set(inspect(engine).get_table_names()) >= PHASE0_TABLES
    engine.dispose()
