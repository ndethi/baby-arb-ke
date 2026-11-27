"""Drop caption parsing and the pricing warning. The price is never guessed."""

from __future__ import annotations

import pytest
from baby_arb.marketing.intake import parse_line, parse_price, price_warnings


@pytest.mark.parametrize(
    ("token", "expected"),
    [("2000", 2000), ("2,000", 2000), ("2k", 2000), ("2.5k", 2500), ("KES2000", 2000),
     ("ksh1500", 1500), ("abc", None), ("0", None), ("2.5", None)],
)
def test_parse_price(token, expected):
    assert parse_price(token) == expected


def test_spec_example():
    p = parse_line("2000 B 0-36m washed, small mark on strap")
    assert (p.kind, p.price, p.grade, p.age_range) == ("own", 2000, "B", "0-36m")
    assert p.notes == "washed, small mark on strap"


def test_price_only():
    p = parse_line("3500")
    assert p.price == 3500 and p.grade is None and p.notes is None


def test_kes_prefix_with_space():
    assert parse_line("KES 2,500 A").price == 2500


def test_missing_price_is_none_not_guessed():
    p = parse_line("stroller 2000 washed")
    assert p.price is None
    assert p.notes == "stroller 2000 washed"


def test_empty_caption():
    p = parse_line(None)
    assert p.price is None and p.notes is None


def test_lowercase_article_is_not_a_grade():
    p = parse_line("1800 a bit worn")
    assert p.grade is None and p.notes == "a bit worn"


def test_spaced_age_range():
    assert parse_line("1800 C 6 - 12 months fine").age_range == "6-12months"


def test_buy_and_ref_tokens():
    p = parse_line("2000 B buy 600 ref 8,500 washed")
    assert p.buy_price == 600 and p.ref_new_price == 8500
    assert p.notes == "washed"


def test_seller_line():
    p = parse_line("#seller 4500 Mary barely used")
    assert (p.kind, p.price, p.seller_name, p.notes) == ("seller", 4500, "Mary", "barely used")


def test_seller_line_missing_name():
    p = parse_line("#seller 4500")
    assert "seller name missing" in p.problems


def test_price_warning_below_3x_buy():
    assert price_warnings(1500, 600) == [
        "Price KES 1,500 is below 3x the buy price (KES 600)."
    ]
    assert price_warnings(1800, 600) == []
    assert price_warnings(1500, None) == []
