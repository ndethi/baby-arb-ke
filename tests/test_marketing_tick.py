"""cal tick: reminders, MISSED, scheduled messages; idempotent; silent when paused."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
import pytest
import respx
from baby_arb.marketing import pipeline as pl
from baby_arb.marketing.bot.auth import Access
from baby_arb.marketing.bot.send import API_BASE, DestinationNotAllowedError, OpsSender
from baby_arb.marketing.tick import build_digest, tick
from baby_arb.posting.store import set_flag
from baby_arb.posting.tables import ScheduleRow
from sqlmodel import Session, select

from tests.test_marketing_pipeline import CFG, PHOTO, fake_renderer, model

NBO = ZoneInfo("Africa/Nairobi")
OPS = -1001


class FakeNotifier:
    def __init__(self):
        self.sent: list[tuple[str, object]] = []

    def send_message(self, chat_id, text, reply_markup=None):
        assert chat_id == OPS
        self.sent.append(("text", text))
        return {}

    def send_media_group(self, chat_id, paths, caption=None):
        assert chat_id == OPS and all(Path(p).is_file() for p in paths)
        self.sent.append(("album", [Path(p).name for p in paths]))
        return []


def _ctx(session, tmp_path, now):
    return pl.Context(session=session, cfg=CFG, assets_dir=tmp_path / "a", actor="111",
                      now=now, renderer=fake_renderer, completer=model())


def _approved(session, tmp_path, now, line="2000 B", title="Graco Modes stroller"):
    ctx = _ctx(session, tmp_path, now)
    step = pl.intake(ctx, [PHOTO], line)
    step = pl.answer(ctx, step.code, "title", title)
    step = pl.override(ctx, step.code)
    pl.approve(ctx, step.code)
    return step.code


@pytest.fixture
def no_digests(monkeypatch):
    """Reminder tests run near 18:30; keep the daily digest out of the way."""
    monkeypatch.setattr("baby_arb.marketing.tick.DIGESTS", ())


WED = datetime(2026, 11, 25, 9, 0, tzinfo=NBO)
THU_SLOT = datetime(2026, 11, 26, 19, 0, tzinfo=NBO)


def test_reminder_at_slot_time_once(db_engine, tmp_path, no_digests):
    with Session(db_engine) as s:
        code = _approved(s, tmp_path, WED)
        note = FakeNotifier()
        assert tick(s, CFG, note, OPS, THU_SLOT - timedelta(minutes=5)) == []
        assert note.sent == []
        assert tick(s, CFG, note, OPS, THU_SLOT + timedelta(minutes=1)) == [f"reminded {code}"]
        kinds = [k for k, _ in note.sent]
        assert kinds == ["album", "text", "text", "text"]
        assert "Time to post P-0001" in note.sent[-1][1]
        # Idempotent.
        assert tick(s, CFG, note, OPS, THU_SLOT + timedelta(minutes=6)) == []
        assert len(note.sent) == 4


def test_missed_after_two_hours_then_reslot(db_engine, tmp_path, no_digests):
    with Session(db_engine) as s:
        code = _approved(s, tmp_path, WED)
        note = FakeNotifier()
        tick(s, CFG, note, OPS, THU_SLOT)
        assert tick(s, CFG, note, OPS, THU_SLOT + timedelta(minutes=119)) == []
        assert tick(s, CFG, note, OPS, THU_SLOT + timedelta(minutes=121)) == [f"missed {code}"]
        assert s.exec(select(ScheduleRow)).one().status == "MISSED"
        assert "wasn't marked posted" in note.sent[-1][1]
        assert tick(s, CFG, note, OPS, THU_SLOT + timedelta(minutes=200)) == []
        ctx = _ctx(s, tmp_path, THU_SLOT + timedelta(hours=3))
        text = pl.reslot(ctx, code)
        assert "Thu 03 Dec" in text
        row = s.exec(select(ScheduleRow)).one()
        assert row.status == "QUEUED" and row.reminded_at is None


def test_posted_before_missed(db_engine, tmp_path, no_digests):
    with Session(db_engine) as s:
        code = _approved(s, tmp_path, WED)
        tick(s, CFG, FakeNotifier(), OPS, THU_SLOT)
        pl.posted(_ctx(s, tmp_path, THU_SLOT), code)
        assert tick(s, CFG, FakeNotifier(), OPS, THU_SLOT + timedelta(hours=3)) == []


def test_paused_sends_nothing(db_engine, tmp_path, no_digests):
    with Session(db_engine) as s:
        _approved(s, tmp_path, WED)
        set_flag(s, "paused", "1")
        s.commit()
        note = FakeNotifier()
        assert tick(s, CFG, note, OPS, THU_SLOT + timedelta(minutes=1)) == []
        assert note.sent == []


def test_monday_week_message_once(db_engine, tmp_path):
    mon = datetime(2026, 11, 30, 8, 5, tzinfo=NBO)
    with Session(db_engine) as s:
        note = FakeNotifier()
        assert tick(s, CFG, note, OPS, mon) == ["sent monday_week"]
        assert note.sent[0][1].startswith("This week's slots:")
        assert tick(s, CFG, note, OPS, mon + timedelta(minutes=5)) == []
        assert tick(s, CFG, note, OPS, datetime(2026, 11, 30, 7, 55, tzinfo=NBO)) == []


def test_daily_tomorrow_lists_queue(db_engine, tmp_path):
    with Session(db_engine) as s:
        _approved(s, tmp_path, WED)
        text = build_digest("daily_tomorrow", s, CFG, datetime(2026, 11, 25, 18, 30,
                                                                tzinfo=NBO))
        assert text is not None and "19:00 drop: P-0001 (approved)" in text
        assert "5 of 6 places empty" in text


def test_daily_tomorrow_silent_on_sunday_eve(db_engine):
    with Session(db_engine) as s:
        # Sat evening -> Sunday is a blackout day with nothing queued.
        assert build_digest("daily_tomorrow", s, CFG,
                            datetime(2026, 11, 28, 18, 30, tzinfo=NBO)) is None


def test_wednesday_drop_nudge_only_when_under_half(db_engine, tmp_path):
    wed_eve = datetime(2026, 11, 25, 18, 0, tzinfo=NBO)
    with Session(db_engine) as s:
        text = build_digest("wednesday_drop", s, CFG, wed_eve)
        assert text is not None and "6 of 6 slots still empty" in text
        for title in ("Graco Modes stroller", "Chicco stroller", "Joie stroller"):
            _approved(s, tmp_path, WED, title=title)
        assert build_digest("wednesday_drop", s, CFG, wed_eve) is None


def test_sunday_review_prompt(db_engine):
    with Session(db_engine) as s:
        note = FakeNotifier()
        done = tick(s, CFG, note, OPS, datetime(2026, 11, 29, 16, 1, tzinfo=NBO))
        assert done == ["sent sunday_review"]


# --------------------------------------------------------------------------- sender

def test_album_sender_refuses_other_chats(tmp_path):
    sender = OpsSender("123:t", Access(frozenset({1}), frozenset({OPS})))
    img = tmp_path / "a.png"
    img.write_bytes(b"png")
    with pytest.raises(DestinationNotAllowedError):
        sender.send_media_group(555, [img])


@respx.mock
def test_album_sender_posts_multipart(tmp_path):
    route = respx.post(f"{API_BASE}/bot123:t/sendMediaGroup").mock(
        return_value=httpx.Response(200, json={"ok": True, "result": [{"message_id": 1}]}))
    sender = OpsSender("123:t", Access(frozenset({1}), frozenset({OPS})))
    imgs = []
    for i in range(2):
        p = tmp_path / f"{i}.png"
        p.write_bytes(b"png")
        imgs.append(p)
    assert sender.send_media_group(OPS, imgs, caption="P-0001") == [{"message_id": 1}]
    body = route.calls[0].request.content
    assert b"attach://f0" in body and b"attach://f1" in body and b"P-0001" in body
