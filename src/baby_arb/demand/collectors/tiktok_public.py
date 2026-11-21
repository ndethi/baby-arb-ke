"""TikTok collector for public hashtag/search data (no login required)."""

from __future__ import annotations

from typing import Any

import structlog

from baby_arb.demand.collectors.base import BaseCollector
from baby_arb.models.demand import DemandSignals

logger = structlog.get_logger()

NOT_BUILT_REASON = (
    "TikTok public search not built; needs Apify/Phyllo (docs/live_scraping_plan.md Phase 4)"
)


class TikTokPublicCollector(BaseCollector):
    """Collect demand signals from TikTok using public search (no login)."""

    def __init__(self, rate_limit_per_second: float = 0.5):
        super().__init__("tiktok_public", rate_limit_per_second)
        self.base_url = "https://www.tiktok.com"
        # Common Kenyan baby-related hashtags to start with
        self.priority_hashtags = [
            "#babydeclutteringke",
            "#secondhandbabyke",
            "#mombusinesske",
            "#babyclotheske",
            "#babytoyske",
            "#strollerke",
            "#carseatke",
            "#babygearke",
            "#handmedownske",
            "#babyfashionke",
        ]

    async def collect(self, product_name: str, **kwargs: Any) -> DemandSignals:
        """Collect demand signals from TikTok public search.

        Returns UNKNOWN until a provider (Apify/Phyllo) is wired in Phase 4.
        Never returns placeholder mention counts.
        """
        self.logger.info("Collecting TikTok public signals", product=product_name)
        return self._unknown(NOT_BUILT_REASON)
