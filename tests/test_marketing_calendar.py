"""Content calendar (ENGINE_SPEC sections 4 and 11). Fixed config, fixed times."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from baby_arb.marketing.calendar import (
    DEFAULT_PATH,
    CalendarConfig,
    format_slot_line,
    format_week,
    load_config,
    move_warnings,
    next_free_slot,
    parse_when,
    slot_kind_for,
    week_view,
)
from baby_arb.posting.tables import Listing, ScheduleRow
from sqlmodel import Session, select

NBO = ZoneInfo("Africa/Nairobi")


def _cfg(**overrides) -> CalendarConfig:
    raw = {
        "timezone": "Africa/Nairobi",
        "channels": ["instagram", "facebook", "tiktok"],
        "slots": {
            "drop": {"days": ["thu"], "time": "19:00", "max": 2},
            "listing": {"days": ["tue", "fri"], "time": "12:30", "max": 2},
            "tip": {"days": ["wed"], "time": "19:00", "max": 1},
            "behind": {"days": ["sat", "sun"], "time": "12:30", "max": 1},
        },
        "blackout_days": ["sun"],
        "min_gap_minutes": 90,
        "lookahead_days": 14,
        "specials": [],
    }
    raw.update(overrides)
    return CalendarConfig.model_validate(raw)


def _nbo(y, m, d, hh=9, mm=0) -> datetime:
    return datetime(y, m, d, hh, mm, tzinfo=NBO)


def _book(session, code, kind, at, status="QUEUED", channels="instagram,facebook,tiktok"):
    if session.get(Listing, code) is None:
        session.add(Listing(code=code, kind="own", status="SCHEDULED"))
    session.add(
        ScheduleRow(listing_code=code, kind=kind, slot_at=at, channels=channels,
                    status=status, proposed_by="system")
    )
    session.commit()


# Mon 23 Nov 2026 .. Sun 29 Nov 2026
MON = _nbo(2026, 11, 23)


def test_repo_calendar_file_loads():
    cfg = load_config(DEFAULT_PATH)
    assert set(cfg.slots) == {"drop", "listing", "teaser", "tip", "behind"}
    assert cfg.slots["drop"].max == 6
    assert cfg.blackout_days == ["sun"]


def test_bad_time_rejected():
    with pytest.raises(ValueError):
        _cfg(slots={"drop": {"days": ["thu"], "time": "25:00", "max": 1}})


@pytest.mark.parametrize(
    ("code", "kind", "expected"),
    [("P-0007", None, "drop"), ("L-0002", None, "listing"), ("C-0001", "tip", "tip")],
)
def test_slot_kind_for(code, kind, expected):
    assert slot_kind_for(code, kind) == expected


def test_slot_kind_for_content_needs_kind():
    with pytest.raises(ValueError):
        slot_kind_for("C-0001")


def test_next_free_slot_is_next_rhythm_day(db_engine):
    with Session(db_engine) as s:
        slot = next_free_slot(s, _cfg(), "listing", MON)
    assert slot is not None
    assert slot.at == _nbo(2026, 11, 24, 12, 30)
    assert slot.filled == 0


def test_full_slot_rolls_to_next_day_of_kind(db_engine):
    with Session(db_engine) as s:
        tue = _nbo(2026, 11, 24, 12, 30)
        _book(s, "L-0001", "listing", tue)
        _book(s, "L-0002", "listing", tue)
        slot = next_free_slot(s, _cfg(), "listing", MON)
    assert slot is not None and slot.at == _nbo(2026, 11, 27, 12, 30)


def test_full_week_rolls_to_next_week(db_engine):
    with Session(db_engine) as s:
        thu = _nbo(2026, 11, 26, 19, 0)
        _book(s, "P-0001", "drop", thu)
        _book(s, "P-0002", "drop", thu)
        slot = next_free_slot(s, _cfg(), "drop", MON)
    assert slot is not None and slot.at == _nbo(2026, 12, 3, 19, 0)


def test_blackout_day_is_skipped(db_engine):
    with Session(db_engine) as s:
        sat = _nbo(2026, 11, 28, 12, 30)
        _book(s, "C-0001", "behind", sat)
        slot = next_free_slot(s, _cfg(), "behind", MON)
    # Sunday is in behind.days but blacked out: next is the following Saturday.
    assert slot is not None and slot.at == _nbo(2026, 12, 5, 12, 30)


def test_past_slot_skipped(db_engine):
    with Session(db_engine) as s:
        slot = next_free_slot(s, _cfg(), "listing", _nbo(2026, 11, 24, 12, 30))
    assert slot is not None and slot.at == _nbo(2026, 11, 27, 12, 30)


def test_special_replaces_regular_slot_and_counts_off_rhythm(db_engine):
    cfg = _cfg(specials=[
        {"date": "2026-11-27", "kind": "listing", "time": "13:00", "label": "Black Friday"},
        {"date": "2026-11-29", "kind": "drop", "time": "19:00", "label": "Sunday special"},
    ])
    with Session(db_engine) as s:
        tue = _nbo(2026, 11, 24, 12, 30)
        _book(s, "L-0001", "listing", tue)
        _book(s, "L-0002", "listing", tue)
        listing = next_free_slot(s, cfg, "listing", MON)
        drop = next_free_slot(s, cfg, "drop", _nbo(2026, 11, 27))
    assert listing is not None and listing.at == _nbo(2026, 11, 27, 13, 0)
    assert listing.label == "Black Friday"
    assert drop is not None and drop.at == _nbo(2026, 11, 29, 19, 0)


def test_min_gap_enforced_on_shared_channel(db_engine):
    with Session(db_engine) as s:
        # A moved post at Tue 12:00 blocks the Tue 12:30 listing slot.
        _book(s, "P-0009", "drop", _nbo(2026, 11, 24, 12, 0))
        slot = next_free_slot(s, _cfg(), "listing", MON)
        assert slot is not None and slot.at == _nbo(2026, 11, 27, 12, 30)
        # Only TikTok in common? Still a clash. A channel not shared is fine.
        fb_only = next_free_slot(s, _cfg(), "listing", MON, channels=["whatsapp"])
    assert fb_only is not None and fb_only.at == _nbo(2026, 11, 24, 12, 30)


def test_skipped_rows_free_their_place(db_engine):
    with Session(db_engine) as s:
        tue = _nbo(2026, 11, 24, 12, 30)
        _book(s, "L-0001", "listing", tue, status="SKIPPED")
        _book(s, "L-0002", "listing", tue, status="MISSED")
        _book(s, "L-0003", "listing", tue)
        slot = next_free_slot(s, _cfg(), "listing", MON)
    assert slot is not None and slot.at == tue and slot.filled == 1


def test_no_slot_in_lookahead_returns_none(db_engine):
    with Session(db_engine) as s:
        assert next_free_slot(s, _cfg(lookahead_days=1), "drop", MON) is None


def test_move_over_max_warns_but_reports(db_engine):
    cfg = _cfg()
    with Session(db_engine) as s:
        thu = _nbo(2026, 11, 26, 19, 0)
        _book(s, "P-0001", "drop", thu)
        _book(s, "P-0002", "drop", thu)
        warnings = move_warnings(s, cfg, "drop", thu, {"instagram"})
        off = move_warnings(s, cfg, "drop", _nbo(2026, 11, 27, 19, 0), {"instagram"})
    assert any("over max" in w for w in warnings)
    assert any("off-rhythm" in w for w in off)


def test_week_view_and_slot_line(db_engine):
    cfg = _cfg()
    with Session(db_engine) as s:
        _book(s, "L-0001", "listing", _nbo(2026, 11, 24, 12, 30))
        view = week_view(s, cfg, date(2026, 11, 25))
    kinds = [(v.slot.kind, v.slot.at.strftime("%a %H:%M"), v.slot.filled) for v in view]
    assert kinds == [
        ("listing", "Tue 12:30", 1),
        ("tip", "Wed 19:00", 0),
        ("drop", "Thu 19:00", 0),
        ("listing", "Fri 12:30", 0),
        ("behind", "Sat 12:30", 0),
    ]
    assert format_slot_line(view[0].slot) == "Slot: Tue 24 Nov, 12:30 (listing 2/2)"


GOLDEN_WEEK = """This week's slots:
🟨 Tue 24 Nov 12:30 listing 1/2: L-0001
⬜ Wed 25 Nov 19:00 tip 0/1: empty
✅ Thu 26 Nov 19:00 drop 2/2: P-0001, P-0002
⬜ Fri 27 Nov 12:30 listing 0/2: empty · Black Friday
⬜ Sat 28 Nov 12:30 behind 0/1: empty
Needs stock: behind, listing, tip"""


def test_golden_week_message(db_engine):
    cfg = _cfg(specials=[{"date": "2026-11-27", "kind": "listing", "time": "12:30",
                          "label": "Black Friday"}])
    with Session(db_engine) as s:
        _book(s, "L-0001", "listing", _nbo(2026, 11, 24, 12, 30))
        _book(s, "P-0001", "drop", _nbo(2026, 11, 26, 19, 0))
        _book(s, "P-0002", "drop", _nbo(2026, 11, 26, 19, 0))
        text = format_week(week_view(s, cfg, date(2026, 11, 23)))
    assert text == GOLDEN_WEEK


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("fri 19:00", _nbo(2026, 11, 27, 19, 0)),
        ("wed 08:00", _nbo(2026, 12, 2, 8, 0)),  # today is Wed 25 Nov 09:00, so next week
        ("wed 10:00", _nbo(2026, 11, 25, 10, 0)),
        ("tomorrow 12:30", _nbo(2026, 11, 26, 12, 30)),
        ("2026-12-01 19:00", _nbo(2026, 12, 1, 19, 0)),
        ("18:30", _nbo(2026, 11, 25, 18, 30)),
    ],
)
def test_parse_when(text, expected):
    assert parse_when(text, _nbo(2026, 11, 25, 9, 0), _cfg()) == expected


def test_parse_when_rejects_nonsense():
    with pytest.raises(ValueError):
        parse_when("next friday-ish", _nbo(2026, 11, 25), _cfg())


def test_stored_times_round_trip_as_utc(db_engine):
    at = _nbo(2026, 11, 24, 12, 30)
    with Session(db_engine) as s:
        _book(s, "L-0001", "listing", at)
        slot = next_free_slot(s, _cfg(), "listing", MON)
        stored = s.exec(select(ScheduleRow)).one().slot_at
    assert slot is not None and slot.filled == 1
    assert stored == at and stored.utcoffset() == timedelta(0)
    assert stored.hour == 9  # 12:30 Nairobi is 09:30 UTC
