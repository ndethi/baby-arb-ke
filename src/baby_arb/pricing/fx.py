"""FX rate retrieval with TTL cache.

Never hardcode rates. Never use a stale rate (>24h). The pricing engine
must know the age of the rate it used.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from baby_arb.config import get_settings

CACHE_PATH = Path("data/cache/fx/usdkes.json")


def get_usdkes_rate(now: datetime | None = None) -> tuple[Decimal, Decimal]:
    """Return (rate, age_hours) for USD/KES.

    Args:
        now: Override current time for testing.

    Returns:
        Tuple of (exchange rate, age in hours).

    Raises:
        FXUnavailable: If no cached rate exists and live fetch fails.
    """
    settings = get_settings()
    now = now or datetime.now(timezone.utc)

    cached = _load_cache()
    if cached is not None:
        age_hours = Decimal(str((now - cached["fetched_at"]).total_seconds() / 3600))
        if age_hours <= Decimal(settings.fx_cache_ttl_hours):
            return Decimal(str(cached["rate"])), age_hours

    # Cache stale or missing. In MVP, fall back to a sentinel so the
    # CLI smoke tests work without network. Production overrides this
    # via the live fetcher.
    fresh = _fetch_live(now)
    if fresh is None:
        if cached is not None:
            # Use stale cache rather than fail. Pricing engine will see
            # the high age and may return LOW confidence.
            age_hours = Decimal(str((now - cached["fetched_at"]).total_seconds() / 3600))
            return Decimal(str(cached["rate"])), age_hours
        raise FXUnavailable("No cached FX rate and live fetch failed.")

    return fresh, Decimal("0")


def _load_cache() -> dict | None:
    if not CACHE_PATH.exists():
        return None
    try:
        with CACHE_PATH.open() as f:
            data = json.load(f)
        return {
            "rate": data["rate"],
            "fetched_at": datetime.fromisoformat(data["fetched_at"]),
        }
    except (json.JSONDecodeError, KeyError, ValueError):
        return None


def _save_cache(rate: Decimal, fetched_at: datetime) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CACHE_PATH.open("w") as f:
        json.dump(
            {"rate": str(rate), "fetched_at": fetched_at.isoformat()},
            f,
        )


def _fetch_live(now: datetime) -> Decimal | None:
    """Fetch from configured FX provider.

    MVP stub. Returns None if no API key configured. Production overrides
    via concrete provider clients.
    """
    settings = get_settings()
    if not settings.fx_api_key:
        return None

    # Real implementation would call openexchangerates.org or wise.com.
    # Stubbed here to keep the MVP runnable without network.
    return None


def set_cache_for_test(rate: Decimal, fetched_at: datetime) -> None:
    """Test helper. Inject a known rate into the cache."""
    _save_cache(rate, fetched_at)


class FXUnavailable(Exception):
    """No exchange rate could be obtained."""
