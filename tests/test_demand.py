"""Demand aggregator tests."""

from __future__ import annotations

from decimal import Decimal

from baby_arb.demand.aggregator import compose_signal
from baby_arb.models.demand import DemandSignals


class TestComposeSignal:
    def test_strong_demand_yields_high_score(self):
        signals = DemandSignals(
            jiji_active_listings=2,
            jiji_sold_30d=14,
            jiji_median_sold_kes=Decimal("32500"),
            jumia_stock="out_of_stock",
            jumia_weeks_out_of_stock=6,
            fb_group_mentions_30d=23,
            fb_group_intent_score=Decimal("0.75"),
            ig_kenyan_mentions_30d=40,
            tiktok_kenyan_mentions_30d=10,
            pigiame_volume=80,
        )
        result = compose_signal("NUNA PIPA", signals)
        assert result.demand_score >= Decimal("0.6")
        assert result.confidence == "HIGH"
        assert result.recommendation is not None
        assert "PURSUE" in result.recommendation

    def test_no_signals_low_confidence(self):
        signals = DemandSignals()
        result = compose_signal("Unknown product", signals)
        assert result.confidence == "LOW"
        assert len(result.missing_data) >= 5

    def test_supply_tightness_high_score(self):
        # 2 active, 20 sold → very tight
        signals = DemandSignals(
            jiji_active_listings=2,
            jiji_sold_30d=20,
            fb_group_intent_score=Decimal("0.5"),
        )
        result = compose_signal("X", signals)
        # The supply/demand ratio sub-score should max out
        assert result.demand_score > Decimal("0.5")

    def test_supply_glut_low_score(self):
        # 30 active, 2 sold → market saturated
        signals = DemandSignals(
            jiji_active_listings=30,
            jiji_sold_30d=2,
            fb_group_intent_score=Decimal("0.2"),
        )
        result = compose_signal("Y", signals)
        assert result.demand_score < Decimal("0.5")
