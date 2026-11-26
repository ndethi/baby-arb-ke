"""Facebook group demand signal collector."""

from __future__ import annotations

from typing import Any

import structlog

from baby_arb.demand.collectors.base import BaseCollector
from baby_arb.models.demand import DemandSignals

logger = structlog.get_logger()

NOT_BUILT_REASON = (
    "Facebook groups need a login; manual entry via `demand score` until "
    "Phase 4 (docs/live_scraping_plan.md)"
)


class FacebookCollector(BaseCollector):
    """Collect demand signals from Facebook parenting groups."""

    def __init__(self, rate_limit_per_second: float = 0.5):
        super().__init__("facebook", rate_limit_per_second)

    async def collect(self, product_name: str, **kwargs: Any) -> DemandSignals:
        """Collect demand signals from Facebook groups.

        Returns UNKNOWN: there is no login-free source for group posts.
        """
        self.logger.info("Collecting Facebook signals", product=product_name)
        return self._unknown(NOT_BUILT_REASON)
