"""Phase 2 identify + lookup inside the drop flow (fake identifier and lookup)."""

from __future__ import annotations

import pytest
from baby_arb.marketing import pipeline as pl
from baby_arb.marketing.identify import Identification
from baby_arb.marketing.lookup import Fact, LookupResult, PriceRef
from baby_arb.posting.tables import EditEvent, Listing
from sqlmodel import Session, select

from tests.test_marketing_pipeline import CFG, NOW, PHOTO, fake_renderer, model

WALKER = Identification(brand="HUANGER", category="push_walker", item_name="Music Walker",
                        age_range="6m+", confidence=0.95)
SHOP = "https://www.jumia.co.ke/huanger-music-walker.html"


def _found(*_a):
    return LookupResult(
        facts=[Fact("Age range", "6-36 months", "https://maker.example.com/walker")],
        price_ref=PriceRef(6499, SHOP, "Huanger Music Walker"))


@pytest.fixture
def ctx(db_engine, tmp_path):
    with Session(db_engine) as session:
        yield pl.Context(session=session, cfg=CFG, assets_dir=tmp_path / "a", actor="111",
                         now=NOW, renderer=fake_renderer, completer=model(),
                         identifier=lambda photos: WALKER, lookup=_found)


def test_confident_identification_goes_straight_to_preview(ctx):
    step = pl.intake(ctx, [PHOTO], "#test 2000 B")
    assert isinstance(step, pl.Preview)
    listing = ctx.session.get(Listing, step.code)
    assert (listing.title, listing.model_source, listing.category) == (
        "Huanger Music Walker", "auto", "push_walker")
    assert listing.age_range == "6m+" and listing.price == 2000
    assert step.info[0].startswith("Item: Huanger Music Walker (auto, 95%)")
    assert "Age range: 6-36 months (maker.example.com)" in step.info
    assert "Seen new at KES 6,499 on jumia.co.ke." in step.info
    assert step.price_ref == 6499
    # The box's 6m+ wins over the shop page's age range in captions.
    assert "6m+" in step.caption_ig and "6-36 months" not in step.caption_ig
    # Push walker is REVIEW (walker type), never BLOCK.
    assert step.needs_check


def test_price_ref_used_only_when_admin_taps(ctx):
    step = pl.intake(ctx, [PHOTO], "2000 B")
    assert ctx.session.get(Listing, step.code).ref_new_price is None
    step = pl.use_price_ref(ctx, step.code)
    listing = ctx.session.get(Listing, step.code)
    assert listing.ref_new_price == 6499 and listing.price == 2000
    assert step.price_ref is None  # adopted, no longer offered
    assert "New in Nairobi from KES 6,499" in step.caption_ig


def test_low_confidence_asks_and_yes_accepts(ctx):
    ctx.identifier = lambda photos: Identification(
        brand="HUANGER", category="push_walker", item_name="Music Walker", confidence=0.5)
    step = pl.intake(ctx, [PHOTO], "2000")
    assert isinstance(step, pl.Need) and step.what == "title"
    assert "looks like Huanger Music Walker (push walker), right?" in step.message
    step = pl.answer(ctx, step.code, "title", "Yes")
    assert isinstance(step, pl.Preview)
    listing = ctx.session.get(Listing, step.code)
    assert listing.title == "Huanger Music Walker" and listing.model_source == "admin"
    assert ctx.session.exec(select(EditEvent)).all() == []


def test_correction_is_logged_as_drift(ctx):
    ctx.identifier = lambda photos: Identification(
        brand="Chicco", category="push_walker", item_name="Walker", confidence=0.4)
    step = pl.intake(ctx, [PHOTO], "2000")
    pl.answer(ctx, step.code, "title", "Huanger Music Walker")
    event = ctx.session.exec(select(EditEvent)).one()
    assert (event.op, event.before, event.after, event.parsed_by) == (
        "correct_model", "Chicco Walker", "Huanger Music Walker", "admin")


def test_editing_an_auto_title_is_logged_as_correct_model(ctx):
    step = pl.intake(ctx, [PHOTO], "2000")
    pl.edit(ctx, step.code, "title Huanger 2-in-1 Music Walker")
    ops = [e.op for e in ctx.session.exec(select(EditEvent))]
    assert ops == ["correct_model", "set_field"]


def test_seated_walker_category_blocks(ctx):
    ctx.identifier = lambda photos: Identification(
        brand="Chicco", category="seated_walker", item_name="Walky Talky", confidence=0.9)
    step = pl.intake(ctx, [PHOTO], "2000")
    assert isinstance(step, pl.Blocked) and "seated_walker" in step.reasons


def test_failed_identification_falls_back_to_question(ctx):
    ctx.identifier = lambda photos: Identification(degraded=True, reason="capped")
    step = pl.intake(ctx, [PHOTO], "2000")
    assert isinstance(step, pl.Need) and "what is it?" in step.message


def test_identify_and_lookup_run_once(ctx):
    calls = {"id": 0, "look": 0}

    def ident(photos):
        calls["id"] += 1
        return Identification(brand="X", item_name="Thing", confidence=0.3)

    def look(*a):
        calls["look"] += 1
        return LookupResult()

    ctx.identifier, ctx.lookup = ident, look
    step = pl.intake(ctx, [PHOTO], "2000")
    with pytest.raises(pl.FlowError):
        pl.answer(ctx, step.code, "title", "no")
    pl.answer(ctx, step.code, "title", "Graco Modes stroller")
    assert calls == {"id": 1, "look": 1}



def test_caption_facts_skip_long_values_and_conflicting_age(ctx):
    long = "Piano Keyboard: Four colorful keys play musical notes, sparking creativity and more"
    ctx.lookup = lambda *a: LookupResult(facts=[
        Fact("Age range", "9 months and older", "https://a.example/x"),
        Fact("Features", long, "https://a.example/x"),
        Fact("Batteries", "2 x AA (not included)", "https://a.example/x"),
    ])
    step = pl.intake(ctx, [PHOTO], "2000 B")
    assert "Details: Batteries: 2 x AA (not included)." in step.caption_ig
    assert "9 months" not in step.caption_ig and "Piano" not in step.caption_ig
    assert any(line.startswith("Age range: 9 months and older") for line in step.info)
