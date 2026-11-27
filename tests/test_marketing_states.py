"""Listing and schedule transitions follow ENGINE_SPEC section 6 and are logged."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from baby_arb.marketing.states import TransitionError, move_listing, move_schedule
from baby_arb.posting.tables import Listing, ListingEvent, ScheduleRow
from sqlmodel import Session, select


def test_allowed_path_is_logged(db_engine):
    with Session(db_engine) as s:
        listing = Listing(code="P-0001", kind="own", status="INTAKE")
        s.add(listing)
        for to in ("SCREENED", "RENDERED", "PREVIEW", "EDITING", "PREVIEW", "APPROVED",
                   "SCHEDULED", "LIVE"):
            move_listing(s, listing, to, "111")
        s.commit()
        events = s.exec(select(ListingEvent)).all()
    assert [e.to_status for e in events][-1] == "LIVE"
    assert len(events) == 8 and all(e.actor == "111" for e in events)


@pytest.mark.parametrize(
    ("start", "to"),
    [("BLOCKED", "SCREENED"), ("BLOCKED", "APPROVED"), ("INTAKE", "APPROVED"),
     ("SCREENED", "APPROVED"), ("REJECTED", "PREVIEW")],
)
def test_forbidden_transitions(db_engine, start, to):
    with Session(db_engine) as s:
        listing = Listing(code="P-0001", kind="own", status=start)
        with pytest.raises(TransitionError):
            move_listing(s, listing, to, "system")


def test_schedule_transitions(db_engine):
    with Session(db_engine) as s:
        s.add(Listing(code="P-0001", kind="own", status="SCHEDULED"))
        row = ScheduleRow(listing_code="P-0001", kind="drop", slot_at=datetime(2026, 11, 26,
                          16, tzinfo=UTC), channels="instagram", status="PROPOSED",
                          proposed_by="system")
        s.add(row)
        s.flush()
        move_schedule(s, row, "QUEUED", "111")
        move_schedule(s, row, "MISSED", "system")
        move_schedule(s, row, "QUEUED", "111", note="re-slotted")
        move_schedule(s, row, "POSTED", "111")
        assert row.posted_at is not None
        with pytest.raises(TransitionError):
            move_schedule(s, row, "QUEUED", "111")
