"""Run demand collectors and merge their signals.

One merge path for the CLI and the ops scripts, so a failing or unbuilt
source always surfaces as an UNKNOWN reason instead of a default value.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence

import structlog

from baby_arb.demand.collectors.base import BaseCollector
from baby_arb.models.demand import DemandSignals

logger = structlog.get_logger()

_METADATA_FIELDS = {"entered_by", "entered_at", "unknown_reasons"}


def merge_signals(into: DemandSignals, other: DemandSignals) -> None:
    """Copy non-None values and UNKNOWN reasons from `other` into `into`.

    Args:
        into: Accumulated signals, modified in place.
        other: Signals from one collector.
    """
    for field in DemandSignals.model_fields:
        if field in _METADATA_FIELDS:
            continue
        value = getattr(other, field)
        if value is not None:
            setattr(into, field, value)
    into.unknown_reasons.update(other.unknown_reasons)


async def collect_signals(
    product_name: str,
    collectors: Sequence[BaseCollector],
    **kwargs: object,
) -> DemandSignals:
    """Run collectors concurrently and merge their output.

    A collector that raises is recorded as UNKNOWN with the error, never
    silently skipped.

    Args:
        product_name: Product to collect signals for.
        collectors: Collectors to run.
        **kwargs: Passed to each collector (brand, model, category).

    Returns:
        Merged DemandSignals with `unknown_reasons` for every source that
        produced nothing.
    """
    merged = DemandSignals(entered_by="collectors")
    results = await asyncio.gather(
        *(c.collect(product_name, **kwargs) for c in collectors),
        return_exceptions=True,
    )
    for collector, result in zip(collectors, results, strict=True):
        if isinstance(result, BaseException):
            logger.warning("Collector failed", collector=collector.name, error=str(result))
            merged.unknown_reasons[collector.name] = f"collector failed: {result}"
            continue
        merge_signals(merged, result)
    return merged


def default_collectors() -> list[BaseCollector]:
    """Return the KE demand collectors used by the CLI and ops scripts."""
    from baby_arb.demand.collectors import (
        FacebookCollector,
        InstagramPublicCollector,
        JijiCollector,
        TikTokPublicCollector,
    )

    return [
        JijiCollector(),
        FacebookCollector(),
        InstagramPublicCollector(),
        TikTokPublicCollector(),
    ]
