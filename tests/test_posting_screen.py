"""Never-sell safety screen."""

from __future__ import annotations

import pytest
from baby_arb.posting.screen import screen


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("Graco SnugRide car seat 0-12m", "car_seat"),
        ("Chicco carseat base", "car_seat"),
        ("booster seat, like new", "car_seat"),
        ("wooden cot with drawer", "cot_or_crib"),
        ("drop-side crib", "cot_or_crib"),
        ("Fisher-Price Rock 'n Play", "inclined_sleeper"),
        ("Rock \u2019n Play sleeper", "inclined_sleeper"),
        ("Boppy newborn lounger", "lounger"),
        ("DockATot deluxe", "lounger"),
        ("seated walker with toys", "seated_walker"),
        ("baby walker", "seated_walker"),
        ("cot mattress 120x60", "mattress"),
        ("Tommee Tippee bottles x4", "bottle"),
        ("Sophie the giraffe teether", "teether"),
    ],
)
def test_never_sell_items_are_blocked(text, reason):
    result = screen(text)
    assert result.verdict == "BLOCK"
    assert reason in result.reasons
    assert not result.approvable_without_override


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("Ergobaby Omni 360 carrier", "carrier_or_strap"),
        ("BabyBjorn bouncer", "bouncer"),
        ("Angelcare bath seat", "bath_seat"),
        ("Bugaboo Fox 3 stroller", "stroller"),
        ("musical mobile, battery operated", "battery_or_heating"),
        ("bottle warmer", "battery_or_heating"),
        ("magnetic tiles 60pc", "magnets"),
        ("Jellycat plush bunny", "plush"),
        ("VTech push walker", "walker_type_unclear"),
    ],
)
def test_review_items_need_override(text, reason):
    result = screen(text)
    assert result.verdict in {"REVIEW", "BLOCK"}
    if result.verdict == "REVIEW":
        assert reason in result.reasons


def test_block_wins_over_review_and_lists_all_block_reasons():
    result = screen("stroller and car seat travel system with crib")
    assert result.verdict == "BLOCK"
    assert {"car_seat", "cot_or_crib"} <= set(result.reasons)


def test_recall_not_checked_makes_safe_item_review():
    result = screen("wooden stacking rings", "toys")
    assert result.verdict == "REVIEW"
    assert result.reasons == ["recall_not_checked"]
    assert result.recall_source == "not_checked"


def test_pass_only_after_recall_check():
    assert screen("wooden stacking rings", recall_checked=True).verdict == "PASS"


def test_matching_is_word_bounded():
    # "scot" must not trip "cot"; "bottlebrush"-style words are left alone.
    assert screen("Scottish wool blanket", recall_checked=True).verdict == "PASS"
