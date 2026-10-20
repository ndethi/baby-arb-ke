#!/usr/bin/env python3
"""
Multi-source demand collector for baby-arb-ke.
Collects demand signals from TikTok, Instagram, forums, marketplace, and Reddit RSS.
Outputs structured JSON for cron job delivery.
"""

import asyncio
import json
import sys
from datetime import UTC, datetime
from decimal import Decimal

import structlog

# Add src to path
sys.path.insert(0, 'src')

from baby_arb.demand.aggregator import compose_signal
from baby_arb.demand.collect import collect_signals, default_collectors
from baby_arb.demand.collectors.base import BaseCollector
from baby_arb.models.demand import DemandSignals

logger = structlog.get_logger()

PRODUCTS = ["Baby Stroller", "Car Seat", "Baby Toy", "Baby Clothes", "Baby Monitor"]


class ForumCollector(BaseCollector):
    """Collector for forum discussions (BabyCenter, Mumsnet)."""

    def __init__(self, rate_limit_per_second: float = 0.5):
        super().__init__("forum", rate_limit_per_second)

    async def collect(self, product_name: str, **kwargs) -> DemandSignals:
        """Return UNKNOWN until forums move behind `baby-arb collect` (Phase 3)."""
        return self._unknown(
            "forum collector not built; BabyCenter/Mumsnet move behind "
            "`baby-arb collect` in Phase 3 (docs/live_scraping_plan.md)"
        )


class RedditCollector(BaseCollector):
    """Collector for Reddit RSS (r/BabyBumps and related)."""

    def __init__(self, rate_limit_per_second: float = 0.5):
        super().__init__("reddit", rate_limit_per_second)

    async def collect(self, product_name: str, **kwargs) -> DemandSignals:
        """Return UNKNOWN: Reddit blocks most subreddit feeds and nothing parses them yet."""
        return self._unknown(
            "Reddit collector not built; most subreddit feeds are blocked "
            "(docs/references/may-2026-reddit-access-findings.md)"
        )


async def collect_multi_source_demand() -> dict:
    """Collect demand signals from multiple sources and return structured JSON.

    Products and totals with no live signal are reported as UNKNOWN with the
    per-source reasons; no defaults are filled in.
    """
    collectors = [*default_collectors(), ForumCollector(), RedditCollector()]

    product_scores = []
    unknown_reasons: dict[str, str] = {}
    total_mentions = 0
    intent_scores: list[Decimal] = []

    for name in PRODUCTS:
        signals = await collect_signals(name, collectors)
        unknown_reasons.update(signals.unknown_reasons)

        for value in (
            signals.jiji_active_listings,
            signals.fb_group_mentions_30d,
            signals.ig_kenyan_mentions_30d,
            signals.tiktok_kenyan_mentions_30d,
        ):
            if value is not None:
                total_mentions += value
        if signals.fb_group_intent_score is not None:
            intent_scores.append(signals.fb_group_intent_score)

        product_signal = compose_signal(name, signals)
        product_scores.append({
            "product": name,
            "score": None if product_signal.confidence == "UNKNOWN"
            else float(product_signal.demand_score),
            "confidence": product_signal.confidence,
            "recommendation": product_signal.recommendation,
        })

    scored = [p for p in product_scores if p["score"] is not None]
    if scored:
        avg_score = sum(p["score"] for p in scored) / len(scored)
        if avg_score >= 0.7:
            recommendation = "PURSUE"
        elif avg_score >= 0.4:
            recommendation = "WATCH"
        else:
            recommendation = "SKIP"
        # Overall confidence is the weakest product confidence among scored products.
        order = ["LOW", "MEDIUM", "HIGH"]
        confidence = min((p["confidence"] for p in scored), key=order.index)
    else:
        recommendation = "UNKNOWN"
        confidence = "UNKNOWN"

    return {
        "scan_timestamp": datetime.now(UTC).isoformat(),
        "sources": {
            c.name: ({"status": "unknown", "reason": unknown_reasons[c.name]}
                     if c.name in unknown_reasons else {"status": "ok"})
            for c in collectors
        },
        "aggregated_signals": {
            "total_mentions": total_mentions if scored else None,
            "sentiment_score": (
                float(sum(intent_scores) / len(intent_scores)) if intent_scores else None
            ),
            "confidence": confidence,
            "top_models": [],
            "recommendation": recommendation,
        },
        "products": product_scores,
    }


def main():
    """Main entry point for cron job."""
    try:
        result = asyncio.run(collect_multi_source_demand())
        # Output JSON
        print(json.dumps(result, indent=2))
        
        # Also generate a human-readable summary for logging
        print("\n=== Multi-Source Demand Collection Complete ===")
        print(f"Timestamp: {result['scan_timestamp']}")
        print(f"Overall Recommendation: {result['aggregated_signals']['recommendation']}")
        print(f"Confidence: {result['aggregated_signals']['confidence']}")
        sentiment = result['aggregated_signals']['sentiment_score']
        print(f"Sentiment Score: {'UNKNOWN' if sentiment is None else f'{sentiment:.2f}'}")
        print("\nProduct Scores:")
        for product in result["products"]:
            score = "UNKNOWN" if product["score"] is None else f"{product['score']:.3f}"
            print(f"  {product['product']}: {score} ({product['recommendation']})")
        
    except Exception as e:
        logger.error("Failed to run multi-source demand collector", error=str(e))
        # Output error JSON
        error_result = {
            "error": str(e),
            "scan_timestamp": datetime.now(UTC).isoformat()
        }
        print(json.dumps(error_result, indent=2))
        sys.exit(1)

if __name__ == "__main__":
    main()