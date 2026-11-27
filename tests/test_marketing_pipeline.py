"""Drop -> preview -> approve flow with a fake renderer and model (no browser, no network)."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from baby_arb.marketing import pipeline as pl
from baby_arb.marketing.calendar import CalendarConfig
from baby_arb.marketing.llm import LLMResult
from baby_arb.marketing.render.static import RenderResult
from baby_arb.posting.tables import (
    EditEvent,
    Listing,
    Render,
    SafetyVerdictRow,
    ScheduleRow,
    as_utc,
)
from sqlmodel import Session, select

NBO = ZoneInfo("Africa/Nairobi")
NOW = datetime(2026, 11, 25, 9, 0, tzinfo=NBO)  # Wednesday
CFG = CalendarConfig.model_validate({
    "channels": ["instagram", "facebook", "tiktok"],
    "slots": {
        "drop": {"days": ["thu"], "time": "19:00", "max": 6},
        "listing": {"days": ["tue", "fri"], "time": "12:30", "max": 4},
        "tip": {"days": ["wed"], "time": "19:00", "max": 1},
        "teaser": {"days": ["mon"], "time": "19:00", "max": 1},
        "behind": {"days": ["sat"], "time": "12:30", "max": 1},
    },
    "blackout_days": ["sun"],
})
PHOTO = b"\xff\xd8\xff\xe0fakejpeg"


def fake_renderer(view, photos, layout, out_dir: Path) -> RenderResult:
    out_dir.mkdir(parents=True, exist_ok=True)
    result = RenderResult()
    for name in ("feed", "story", "tiktok_1"):
        path = out_dir / f"{name}.png"
        path.write_text(json.dumps({"code": view.code, "price": view.price,
                                    "hero": layout.photo_order[0]}))
        result.paths[name] = path
        result.issues[name] = []
    return result


def model(reply: str | None = None):
    calls: list[str] = []

    def completer(purpose, messages, **_kw):
        calls.append(purpose)
        if reply is None:
            return LLMResult(None, True, "capped")
        return LLMResult(reply, False, None, "fake", "fake")

    completer.calls = calls  # type: ignore[attr-defined]
    return completer


@pytest.fixture
def ctx(db_engine, tmp_path):
    with Session(db_engine) as session:
        yield pl.Context(session=session, cfg=CFG, assets_dir=tmp_path / "assets",
                         actor="111", now=NOW, renderer=fake_renderer, completer=model())


def _to_preview(ctx, line="2000 B 0-36m washed, small mark on strap",
                title="Graco FastAction Fold stroller", photos=3) -> pl.Preview:
    step = pl.intake(ctx, [PHOTO] * photos, line)
    if isinstance(step, pl.Need) and step.what == "title":
        step = pl.answer(ctx, step.code, "title", title)
    assert isinstance(step, pl.Preview), step
    return step


def test_full_happy_path(ctx):
    step = pl.intake(ctx, [PHOTO] * 3, "2000 B 0-36m washed, small mark on strap")
    assert isinstance(step, pl.Need) and step.what == "title" and step.code == "P-0001"
    step = pl.answer(ctx, "P-0001", "title", "Graco FastAction Fold stroller")
    # REVIEW (stroller; recall not checked until Phase 2) goes straight to the preview.
    assert isinstance(step, pl.Preview) and step.needs_check
    assert any("Check before approving" in w and "stroller" in w and "recall not checked" in w
               for w in step.warnings)
    assert step.round == 1 and len(step.assets) == 3
    assert step.slot_line == "Slot: Thu 26 Nov, 19:00 (drop 1/6)"
    assert "KES 2,000" in step.caption_ig and "DM P-0001 to buy" in step.caption_ig

    listing = ctx.session.get(Listing, "P-0001")
    assert listing.status == "PREVIEW" and listing.price == 2000
    assert listing.price_source == "admin"
    assert len(list((ctx.assets_dir / "raw" / "P-0001").iterdir())) == 3
    sched = ctx.session.exec(select(ScheduleRow)).one()
    assert sched.status == "PROPOSED" and sched.kind == "drop"

    verdict = pl.latest_verdict(ctx.session, "P-0001")
    assert verdict.override_by is None
    text = pl.approve(ctx, "P-0001")
    assert "queued for Thu 26 Nov 19:00" in text
    # Approving is the admin's recorded check.
    assert pl.latest_verdict(ctx.session, "P-0001").override_by == "111"
    assert ctx.session.get(Listing, "P-0001").status == "SCHEDULED"
    assert ctx.session.exec(select(ScheduleRow)).one().status == "QUEUED"


def test_missing_price_is_asked_never_guessed(ctx):
    step = pl.intake(ctx, [PHOTO], "stroller 2000 washed")
    assert isinstance(step, pl.Need) and step.what == "price"
    assert ctx.session.get(Listing, "P-0001").price is None
    with pytest.raises(pl.FlowError):
        pl.answer(ctx, "P-0001", "price", "cheap")
    step = pl.answer(ctx, "P-0001", "price", "1,800")
    assert isinstance(step, pl.Need) and step.what == "title"
    assert ctx.session.get(Listing, "P-0001").price == 1800


def test_block_stops_pipeline_and_can_never_be_approved(ctx):
    step = pl.intake(ctx, [PHOTO], "3000 A")
    step = pl.answer(ctx, step.code, "title", "Chicco KeyFit 30 infant car seat")
    assert isinstance(step, pl.Blocked) and step.reasons == ["car_seat"]
    listing = ctx.session.get(Listing, "P-0001")
    assert listing.status == "BLOCKED"
    with pytest.raises(pl.FlowError):
        pl.approve(ctx, "P-0001")
    with pytest.raises(pl.FlowError):
        pl.skip(ctx, "P-0001")
    assert ctx.session.exec(select(Render)).all() == []


def test_photo_count_limits(ctx):
    with pytest.raises(pl.FlowError):
        pl.intake(ctx, [], "2000")
    with pytest.raises(pl.FlowError):
        pl.intake(ctx, [PHOTO] * 7, "2000")


def test_edit_round_logs_drift(ctx):
    _to_preview(ctx)
    step = pl.edit(ctx, "P-0001", "price bigger, drop 'washed', use photo 3 as main")
    assert isinstance(step, pl.Preview) and step.round == 2
    assert step.echo == ["make price badge larger", "remove 'washed' from captions",
                         "set photo 3 as hero"]
    assert "washed" not in step.caption_ig.lower()
    hero = json.loads(step.assets[0].read_text())["hero"]
    assert hero == 3
    events = ctx.session.exec(select(EditEvent)).all()
    assert [e.op for e in events] == ["resize", "rewrite_caption", "swap_photo"]
    assert all(e.round == 1 and e.parsed_by == "rules" for e in events)
    assert ctx.session.get(Listing, "P-0001").status == "PREVIEW"
    # Still one schedule row: the proposed slot is kept across rounds.
    assert len(ctx.session.exec(select(ScheduleRow)).all()) == 1


def test_admin_price_edit_is_kept_and_logged(ctx):
    _to_preview(ctx)
    step = pl.edit(ctx, "P-0001", "price 1800")
    assert isinstance(step, pl.Preview)
    listing = ctx.session.get(Listing, "P-0001")
    assert listing.price == 1800 and listing.price_source == "admin"
    assert "KES 1,800" in listing.caption_ig
    event = ctx.session.exec(select(EditEvent)).one()
    assert (event.op, event.target, event.before, event.after) == ("set_field", "price",
                                                                    "2000", "1800")


def test_model_caption_with_other_price_never_replaces_admin_price(ctx):
    bad = json.dumps({"ig": "Stroller · KES 1,500 · 0-36m\nDM P-0001 to buy",
                      "tiktok": "Stroller KES 1,500 | P-0001\nDM P-0001 to buy\n#a #b #c"})
    ctx.completer = model(bad)
    preview = _to_preview(ctx)
    assert "KES 2,000" in preview.caption_ig and "1,500" not in preview.caption_ig
    assert ctx.session.get(Listing, "P-0001").price == 2000


def test_unclear_edit_asks(ctx):
    _to_preview(ctx)
    step = pl.edit(ctx, "P-0001", "make it pop more")
    assert isinstance(step, pl.Question)
    assert ctx.session.exec(select(EditEvent)).all() == []


def test_edit_that_makes_it_a_car_seat_blocks(ctx):
    _to_preview(ctx)
    step = pl.edit(ctx, "P-0001", "title Graco SnugRide car seat")
    assert isinstance(step, pl.Blocked)
    assert ctx.session.get(Listing, "P-0001").status == "BLOCKED"
    assert ctx.session.exec(select(ScheduleRow)).one().status == "SKIPPED"


def test_new_review_reason_after_edit_is_shown_again(ctx):
    _to_preview(ctx, line="2000 B 0-36m washed")
    step = pl.edit(ctx, "P-0001", "title Ergobaby Omni carrier")
    assert isinstance(step, pl.Preview) and step.needs_check
    assert any("carrier or strap" in w for w in step.warnings)
    verdict = ctx.session.exec(
        select(SafetyVerdictRow).order_by(SafetyVerdictRow.id.desc())).first()
    assert verdict.verdict == "REVIEW" and verdict.override_by is None
    pl.approve(ctx, "P-0001")
    assert pl.latest_verdict(ctx.session, "P-0001").override_by == "111"


def test_test_tag_and_mark_test(ctx):
    step = pl.intake(ctx, [PHOTO], "#test 2000 B")
    step = pl.answer(ctx, step.code, "title", "Graco Modes stroller")
    assert isinstance(step, pl.Preview) and step.is_test
    assert step.warnings[0] == "TEST drop: not a real listing."
    listing = ctx.session.get(Listing, "P-0001")
    assert listing.is_test and listing.price == 2000 and listing.grade == "B"

    _to_preview(ctx)  # P-0002, a real drop
    pl.approve(ctx, "P-0002")
    text = pl.mark_test(ctx, "P-0002")
    assert "marked as a test and closed" in text
    assert ctx.session.get(Listing, "P-0002").status == "REJECTED"
    rows = ctx.session.exec(select(ScheduleRow).where(ScheduleRow.listing_code == "P-0002"))
    assert [r.status for r in rows] == ["SKIPPED"]
    assert ctx.session.exec(select(EditEvent)).all() == []  # not drift


def test_approve_now(ctx):
    _to_preview(ctx)
    pl.approve(ctx, "P-0001", now=True)
    row = ctx.session.exec(select(ScheduleRow)).one()
    assert row.status == "QUEUED" and as_utc(row.slot_at) == as_utc(NOW)
    assert row.moved_from is not None


def test_reject_logs_reason_as_drift(ctx):
    _to_preview(ctx)
    pl.reject(ctx, "P-0001", "photos too dark")
    assert ctx.session.get(Listing, "P-0001").status == "REJECTED"
    event = ctx.session.exec(select(EditEvent)).one()
    assert (event.op, event.raw_text) == ("reject", "photos too dark")
    assert ctx.session.exec(select(ScheduleRow)).one().status == "SKIPPED"


def test_skip_keeps_approved_without_slot(ctx):
    _to_preview(ctx)
    pl.skip(ctx, "P-0001")
    assert ctx.session.get(Listing, "P-0001").status == "APPROVED"
    assert ctx.session.exec(select(ScheduleRow)).one().status == "SKIPPED"
    text = pl.move(ctx, "P-0001", "fri 19:00")
    assert "moved to Fri 27 Nov 19:00" in text and "off-rhythm" in text
    assert ctx.session.get(Listing, "P-0001").status == "SCHEDULED"


def test_move_and_posted(ctx):
    _to_preview(ctx)
    pl.approve(ctx, "P-0001")
    text = pl.move(ctx, "P-0001", "thu 18:00")
    assert "off-rhythm" in text
    row = ctx.session.exec(select(ScheduleRow)).one()
    assert as_utc(row.slot_at).astimezone(NBO).hour == 18 and row.status == "QUEUED"
    pl.posted(ctx, "P-0001")
    listing = ctx.session.get(Listing, "P-0001")
    assert listing.status == "LIVE" and listing.live_at is not None
    assert ctx.session.exec(select(ScheduleRow)).one().status == "POSTED"


def test_seller_listing_gets_l_code_and_listing_slot(ctx):
    step = pl.intake(ctx, [PHOTO], "#seller 4500 Mary barely used")
    assert step.code == "L-0001"
    preview = _finish(ctx, step, "Joie Mimzy high chair")
    assert preview.slot_line.startswith("Slot: Fri 27 Nov, 12:30 (listing 1/4)")
    assert "Seller listing" in preview.caption_ig


def _finish(ctx, step, title):
    if isinstance(step, pl.Need) and step.what == "title":
        step = pl.answer(ctx, step.code, "title", title)
    assert isinstance(step, pl.Preview), step
    return step


def test_content_post_skips_pricing_and_screen(ctx):
    step = pl.intake(ctx, [PHOTO, PHOTO], "How we recall-check every item", content_kind="tip")
    assert isinstance(step, pl.Preview) and step.code == "C-0001"
    assert step.slot_line.startswith("Slot: Wed 25 Nov, 19:00 (tip 1/1)")
    assert "KES" not in step.caption_ig
    pl.approve(ctx, "C-0001")
    assert ctx.session.get(Listing, "C-0001").status == "SCHEDULED"


def test_special_label_kept_across_rounds(db_engine, tmp_path):
    cfg = CalendarConfig.model_validate({**CFG.model_dump(), "specials": [
        {"date": "2026-11-26", "kind": "drop", "time": "19:00", "label": "Gift edition"}]})
    with Session(db_engine) as session:
        ctx = pl.Context(session=session, cfg=cfg, assets_dir=tmp_path / "a", actor="111",
                         now=NOW, renderer=fake_renderer, completer=model())
        first = _to_preview(ctx)
        second = pl.edit(ctx, first.code, "price bigger")
    assert first.slot_line.endswith("· Gift edition")
    assert second.slot_line == first.slot_line
