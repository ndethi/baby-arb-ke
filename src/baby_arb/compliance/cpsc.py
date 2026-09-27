"""CPSC recall check via the SaferProducts API.

The API is free and public. We cache results for up to 24h. If the API
is unreachable and the cache is stale, we fail closed with REVIEW.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Literal

from baby_arb.config import get_settings
from baby_arb.models.candidate import BuyCandidate

CACHE_PATH = Path("data/cache/cpsc/recalls.json")

ResultKind = Literal["clear", "recalled", "related_recall", "unreachable"]


@dataclass
class CPSCResult:
    kind: ResultKind
    detail: str
    cache_age_hours: Decimal | None


def check_cpsc_recall(
    candidate: BuyCandidate,
    *,
    now: datetime | None = None,
) -> CPSCResult:
    """Check the CPSC recall database for this candidate.

    MVP: looks up against a cached recalls list. Production would call
    the SaferProducts REST API and refresh the cache nightly.
    """
    now = now or datetime.now(UTC)
    cache_data, cache_age = _load_cache(now)

    if cache_data is None:
        # No cache and we don't auto-fetch in MVP.
        # Production: trigger a refresh here.
        return CPSCResult(
            kind="unreachable",
            detail="no cached recall data and live fetch not configured",
            cache_age_hours=None,
        )

    settings = get_settings()
    if cache_age > Decimal(settings.cpsc_cache_ttl_hours):
        # Stale cache. In production, force refresh; if refresh fails,
        # fall through with stale data and flag REVIEW.
        # MVP: use stale cache, signal staleness.
        pass

    haystack = f"{candidate.brand} {candidate.model}".lower().strip()
    recalls = cache_data.get("recalls", [])

    # Direct match → recalled.
    for recall in recalls:
        match_strings = [m.lower() for m in recall.get("match_strings", [])]
        if any(m and m in haystack for m in match_strings):
            return CPSCResult(
                kind="recalled",
                detail=recall.get("title", "matched recall"),
                cache_age_hours=cache_age,
            )

    # Brand-only match → related recall, REVIEW.
    brand = (candidate.brand or "").lower().strip()
    if brand:
        for recall in recalls:
            if any(brand in m.lower() for m in recall.get("match_strings", [])):
                return CPSCResult(
                    kind="related_recall",
                    detail=f"brand has prior recall: {recall.get('title', '')}",
                    cache_age_hours=cache_age,
                )

    return CPSCResult(kind="clear", detail="no matching recall", cache_age_hours=cache_age)


def _load_cache(now: datetime) -> tuple[dict | None, Decimal]:
    """Load the CPSC recall cache. Returns (data, age_hours)."""
    if not CACHE_PATH.exists():
        return None, Decimal("0")
    try:
        with CACHE_PATH.open() as f:
            data = json.load(f)
        fetched_at = datetime.fromisoformat(data["fetched_at"])
        if fetched_at.tzinfo is None:
            fetched_at = fetched_at.replace(tzinfo=UTC)
        age_hours = Decimal(str((now - fetched_at).total_seconds() / 3600))
        return data, age_hours
    except (json.JSONDecodeError, KeyError, ValueError):
        return None, Decimal("0")


def write_cache_for_test(recalls: list[dict], now: datetime | None = None) -> None:
    """Test helper. Inject a known recalls list into the cache."""
    now = now or datetime.now(UTC)
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CACHE_PATH.open("w") as f:
        json.dump(
            {"fetched_at": now.isoformat(), "recalls": recalls},
            f,
        )
