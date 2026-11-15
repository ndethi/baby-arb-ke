"""Demand-scout cache entries without live data never reach alerts or briefs."""

from __future__ import annotations

import pytest
from baby_arb.demand.cache import exclusion_reason, split_live_products


def _product(name="Stroller", score=0.7, confidence="HIGH", **signals):
    base = {"entered_by": "collectors", "unknown_reasons": {}}
    base.update(signals)
    return {"name": name, "demand_score": score, "confidence": confidence, "signals": base}


def test_live_product_is_kept():
    assert exclusion_reason(_product()) is None


@pytest.mark.parametrize(
    ("product", "expected"),
    [
        (_product(entered_by="jiji_api_demo"), "demo values"),
        ({"name": "Old", "demand_score": 0.8, "confidence": "HIGH",
          "signals": {"entered_by": "manual"}}, "before demo collectors were removed"),
        (_product(score=None, confidence="UNKNOWN"), "UNKNOWN"),
        (_product(score=0.0, confidence="UNKNOWN"), "UNKNOWN"),
    ],
)
def test_products_without_live_data_are_excluded(product, expected):
    reason = exclusion_reason(product)
    assert reason is not None
    assert expected in reason


def test_split_returns_names_and_reasons():
    live, excluded = split_live_products(
        [_product("A"), _product("B", entered_by="tiktok_public_demo")]
    )
    assert [p["name"] for p in live] == ["A"]
    assert excluded == [("B", "demo values from tiktok_public_demo")]
