"""Pytest fixtures for baby-arb-ke."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from baby_arb.compliance.cpsc import write_cache_for_test
from baby_arb.models.candidate import BuyCandidate, ItemCategory, ItemCondition
from baby_arb.pricing.fx import set_cache_for_test


FIXTURES_DIR = Path(__file__).parent.parent / "data" / "fixtures"


@pytest.fixture(autouse=True)
def isolated_caches(tmp_path, monkeypatch):
    """Redirect cache paths to a tmp dir so tests don't interfere."""
    cache_root = tmp_path / "cache"
    cache_root.mkdir()

    monkeypatch.setattr(
        "baby_arb.pricing.fx.CACHE_PATH",
        cache_root / "fx" / "usdkes.json",
    )
    monkeypatch.setattr(
        "baby_arb.compliance.cpsc.CACHE_PATH",
        cache_root / "cpsc" / "recalls.json",
    )
    yield


@pytest.fixture
def now():
    """Fixed `now` for deterministic tests."""
    return datetime(2026, 5, 10, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def fresh_fx(now):
    """Inject a known FX rate (USD/KES = 145.5) into the cache."""
    set_cache_for_test(Decimal("145.5"), now)
    yield Decimal("145.5")


@pytest.fixture
def empty_cpsc_cache(now):
    """Inject an empty CPSC recall list."""
    write_cache_for_test([], now=now)


@pytest.fixture
def loaded_cpsc_cache(now):
    """Inject the synthetic CPSC fixture."""
    fixture_file = FIXTURES_DIR / "cpsc_recalls_sample.json"
    with fixture_file.open() as f:
        data = json.load(f)
    write_cache_for_test(data["recalls"], now=now)


@pytest.fixture
def standard_carseat_candidate():
    """A typical NUNA car seat candidate."""
    return BuyCandidate(
        candidate_id="test-carseat",
        marketplace="ebay",
        listing_url="https://www.ebay.com/itm/test",
        brand="NUNA",
        model="PIPA Lite RX",
        category=ItemCategory.CAR_SEAT,
        condition_text="Used like new, manufactured 2023, all parts intact",
        condition_normalized=ItemCondition.LIKE_NEW,
        listing_price_usd=Decimal("180"),
        us_shipping_usd=Decimal("22"),
        weight_lb=Decimal("9"),
        weight_source="listed",
        length_in=Decimal("18"),
        width_in=Decimal("18"),
        height_in=Decimal("24"),
        seller_id="seller_test",
        seller_state="TX",
        seller_feedback_count=200,
        seller_feedback_pct=Decimal("99.2"),
        photos=[
            "https://example.com/1.jpg",
            "https://example.com/2.jpg",
            "https://example.com/3.jpg",
            "https://example.com/4.jpg",
        ],
        reference_ke_sale_price_kes=Decimal("32500"),
        reference_source="jiji_median_sold",
        reference_n=5,
    )
