"""Listing store: code allocation and bot flags."""

from __future__ import annotations

from baby_arb.posting.store import is_paused, next_code, set_flag
from sqlmodel import Session


def test_codes_count_per_prefix(db_engine):
    with Session(db_engine) as s:
        assert next_code(s, "P") == "P-0001"
        assert next_code(s, "P") == "P-0002"
        assert next_code(s, "L") == "L-0001"
        s.commit()
    with Session(db_engine) as s:
        assert next_code(s, "P") == "P-0003"


def test_rolled_back_intake_does_not_burn_a_code(db_engine):
    with Session(db_engine) as s:
        next_code(s, "C")
        s.rollback()
    with Session(db_engine) as s:
        assert next_code(s, "C") == "C-0001"


def test_pause_flag(db_engine):
    with Session(db_engine) as s:
        assert not is_paused(s)
        set_flag(s, "paused", "1")
        s.commit()
        assert is_paused(s)
        set_flag(s, "paused", "0")
        s.commit()
        assert not is_paused(s)
