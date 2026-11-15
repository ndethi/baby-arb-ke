"""Filter demand-scout cache entries down to ones backed by live data.

`data/cache/demand_scout/latest.json` is read by the daily alert, the weekly
ideas job and the sourcing brief. Entries written before the collectors
stopped returning demo values (no `unknown_reasons` key), entries tagged by a
`*_demo` collector, and entries with no score are excluded with a reason, so
none of them can reach Telegram or a brief.
"""

from __future__ import annotations

from typing import Any


def exclusion_reason(product: dict[str, Any]) -> str | None:
    """Return why a cached product must not be used, or None if it is usable.

    Args:
        product: One entry of the cache's `products` list.

    Returns:
        A human-readable reason, or None when the entry is backed by live data.
    """
    signals = product.get("signals") or {}
    entered_by = str(signals.get("entered_by", ""))
    if entered_by.endswith("_demo"):
        return f"demo values from {entered_by}"
    if "unknown_reasons" not in signals:
        return "written before demo collectors were removed; may hold demo values"
    if product.get("demand_score") is None or product.get("confidence") == "UNKNOWN":
        return "UNKNOWN: no live demand data"
    return None


def split_live_products(
    products: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[tuple[str, str]]]:
    """Split cached products into usable ones and (name, reason) exclusions.

    Args:
        products: The cache's `products` list.

    Returns:
        (live, excluded): usable products, and the name plus reason for each
        product left out.
    """
    live: list[dict[str, Any]] = []
    excluded: list[tuple[str, str]] = []
    for product in products:
        reason = exclusion_reason(product)
        if reason is None:
            live.append(product)
        else:
            excluded.append((str(product.get("name", "Unknown product")), reason))
    return live, excluded
