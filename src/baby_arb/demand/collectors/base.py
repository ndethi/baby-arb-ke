"""Base class for demand signal collectors."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any, TypeVar

import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from baby_arb.models.demand import DemandSignals

logger = structlog.get_logger()

T = TypeVar("T")


class BaseCollector(ABC):
    """Base class for all demand signal collectors."""

    def __init__(self, name: str, rate_limit_per_second: float = 1.0):
        self.name = name
        self.rate_limit_per_second = rate_limit_per_second
        self.last_call_time = 0.0
        self.logger = logger.bind(collector=name)

    def _rate_limit(self) -> None:
        """Enforce rate limiting between API calls."""
        elapsed = time.time() - self.last_call_time
        min_interval = 1.0 / self.rate_limit_per_second
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        self.last_call_time = time.time()

    @abstractmethod
    async def collect(self, product_name: str, **kwargs: Any) -> DemandSignals:
        """Collect demand signals for a product.

        Args:
            product_name: Name of the product to collect signals for
            **kwargs: Additional collector-specific parameters

        Returns:
            DemandSignals object with collected data
        """
        pass

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    def _safe_api_call(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Wrap API calls with retry logic and rate limiting."""
        self._rate_limit()
        try:
            return func(*args, **kwargs)
        except Exception as e:
            self.logger.warning("API call failed", error=str(e))
            raise

    def _create_empty_signals(self) -> DemandSignals:
        """Create an empty DemandSignals object."""
        return DemandSignals()

    def _unknown(self, reason: str) -> DemandSignals:
        """Return signals with no values and the reason this source is UNKNOWN.

        Collectors must use this instead of inventing values when a source is
        not built, blocked or failed.
        """
        self.logger.info("Source UNKNOWN", reason=reason)
        return DemandSignals(entered_by=self.name, unknown_reasons={self.name: reason})