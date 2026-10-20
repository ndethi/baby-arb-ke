"""Jiji.co.ke demand signal collector."""

from __future__ import annotations

from decimal import Decimal

import structlog

from baby_arb.demand.collectors.base import BaseCollector
from baby_arb.models.demand import DemandSignals

logger = structlog.get_logger()


class JijiCollector(BaseCollector):
    """Collect demand signals from Jiji.co.ke."""

    def __init__(self, rate_limit_per_second: float = 0.5):
        super().__init__("jiji", rate_limit_per_second)
        self.base_url = "https://jiji.co.ke"

    async def collect(self, product_name: str, **kwargs) -> DemandSignals:
        """Collect demand signals from Jiji.

        Note: This is a simplified MVP version. In production, you would:
        1. Use Jiji's official API if available
        2. Or use scraping with proper headers, session management, etc.
        3. Handle JavaScript-rendered content if needed

        For now, we return demo data to demonstrate the structure.
        """
        self.logger.info("Collecting Jiji signals", product=product_name)

        # For MVP, we'll return demo data based on product name
        # In real implementation, this would make HTTP requests to Jiji
        signals = DemandSignals()

        # Simple demo logic - in reality, parse actual search results
        if "stroller" in product_name.lower() or "pushchair" in product_name.lower():
            signals.jiji_active_listings = 12
            signals.jiji_sold_30d = 8
            signals.jiji_median_sold_kes = Decimal("15000")
            signals.entered_by = "jiji_api_demo"
        elif "car seat" in product_name.lower():
            signals.jiji_active_listings = 5
            signals.jiji_sold_30d = 3
            signals.jiji_median_sold_kes = Decimal("8000")
            signals.entered_by = "jiji_api_demo"
        elif "toy" in product_name.lower():
            signals.jiji_active_listings = 25
            signals.jiji_sold_30d = 15
            signals.jiji_median_sold_kes = Decimal("2500")
            signals.entered_by = "jiji_api_demo"
        else:
            # Generic demo data
            signals.jiji_active_listings = 3
            signals.jiji_sold_30d = 2
            signals.jiji_median_sold_kes = Decimal("5000")
            signals.entered_by = "jiji_api_demo"

        return signals