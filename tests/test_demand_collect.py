"""Collectors return UNKNOWN with a reason, never demo values."""

from __future__ import annotations

from decimal import Decimal

import pytest
from baby_arb.demand.collect import collect_signals, default_collectors, merge_signals
from baby_arb.demand.collectors.base import BaseCollector
from baby_arb.models.demand import DemandSignals

SIGNAL_FIELDS = [
    f
    for f in DemandSignals.model_fields
    if f not in {"entered_by", "entered_at", "unknown_reasons"}
]

PRODUCTS = ["Baby Stroller", "Car Seat", "Baby Toy", "Baby Clothes", "Baby Monitor", "Other"]


class _Raising(BaseCollector):
    def __init__(self) -> None:
        super().__init__("raising")

    async def collect(self, product_name: str, **kwargs) -> DemandSignals:
        raise RuntimeError("site layout changed")


class _Observed(BaseCollector):
    def __init__(self) -> None:
        super().__init__("observed")

    async def collect(self, product_name: str, **kwargs) -> DemandSignals:
        return DemandSignals(entered_by="observed", jiji_sold_30d=4)


@pytest.mark.parametrize("product", PRODUCTS)
@pytest.mark.parametrize("collector", default_collectors(), ids=lambda c: c.name)
async def test_unbuilt_collectors_return_unknown(collector, product):
    signals = await collector.collect(product)
    assert all(getattr(signals, f) is None for f in SIGNAL_FIELDS)
    assert signals.unknown_reasons[collector.name]
    assert not signals.entered_by.endswith("_demo")


async def test_collect_signals_has_no_values_and_one_reason_per_source():
    signals = await collect_signals("Baby Stroller", default_collectors())
    assert all(getattr(signals, f) is None for f in SIGNAL_FIELDS)
    assert set(signals.unknown_reasons) == {c.name for c in default_collectors()}


async def test_failing_collector_is_recorded_as_unknown():
    signals = await collect_signals("Baby Stroller", [_Raising(), _Observed()])
    assert signals.unknown_reasons == {"raising": "collector failed: site layout changed"}
    assert signals.jiji_sold_30d == 4


def test_merge_keeps_values_and_reasons():
    into = DemandSignals(unknown_reasons={"a": "down"})
    merge_signals(into, DemandSignals(fb_group_intent_score=Decimal("0.4")))
    merge_signals(into, DemandSignals(unknown_reasons={"b": "blocked"}))
    assert into.fb_group_intent_score == Decimal("0.4")
    assert into.unknown_reasons == {"a": "down", "b": "blocked"}
