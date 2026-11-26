"""Jiji.co.ke demand signal collector."""

from __future__ import annotations

from typing import Any

import structlog

from baby_arb.demand.collectors.base import BaseCollector
from baby_arb.models.demand import DemandSignals

logger = structlog.get_logger()

NOT_BUILT_REASON = (
    "Jiji snapshot collector not built yet (docs/live_scraping_plan.md Phase 2)"
)


class JijiCollector(BaseCollector):
    """Collect demand signals from Jiji.co.ke."""

    def __init__(self, rate_limit_per_second: float = 0.5):
        super().__init__("jiji", rate_limit_per_second)
        self.base_url = "https://jiji.co.ke"

    async def collect(self, product_name: str, **kwargs: Any) -> DemandSignals:
        """Collect demand signals from Jiji.

        Returns UNKNOWN until the daily HTML snapshot collector (Phase 2) exists.
        Never returns placeholder listing counts or KE prices.
        """
        self.logger.info("Collecting Jiji signals", product=product_name)
        return self._unknown(NOT_BUILT_REASON)
