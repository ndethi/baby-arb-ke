#!/usr/bin/env python3
"""
Multi-source demand collector for baby-arb-ke.
Collects demand signals from TikTok, Instagram, forums, marketplace, and Reddit RSS.
Outputs structured JSON for cron job delivery.
"""

import asyncio
import json
import sys
from datetime import datetime, timezone
from decimal import Decimal
import structlog

# Add src to path
sys.path.insert(0, 'src')

from baby_arb.demand.collectors.base import BaseCollector
from baby_arb.demand.collectors.jiji import JijiCollector
from baby_arb.demand.collectors.facebook import FacebookCollector
from baby_arb.demand.collectors.instagram_public import InstagramPublicCollector
from baby_arb.demand.collectors.tiktok_public import TikTokPublicCollector
from baby_arb.demand.aggregator import compose_signal
from baby_arb.models.demand import DemandSignals, ProductSignal

logger = structlog.get_logger()

class ForumCollector(BaseCollector):
    """Collector for forum discussions (BabyCenter, Mumsnet)."""
    
    def __init__(self, rate_limit_per_second: float = 0.5):
        super().__init__("forum", rate_limit_per_second)
        # We'll use demo data for now since actual scraping requires more work
        self.logger = logger.bind(collector="forum")
    
    async def collect(self, product_name: str, **kwargs) -> DemandSignals:
        """Collect demand signals from forums (demo data for MVP)."""
        self.logger.info("Collecting forum signals (demo)", product=product_name)
        
        signals = DemandSignals()
        product_lower = product_name.lower()
        
        # Demo data based on typical forum discussions
        if "stroller" in product_lower:
            signals.fb_group_mentions_30d = 15  # repurposing field for forum mentions
            signals.fb_group_intent_score = Decimal("0.7")
        elif "car seat" in product_lower:
            signals.fb_group_mentions_30d = 10
            signals.fb_group_intent_score = Decimal("0.6")
        elif "toy" in product_lower:
            signals.fb_group_mentions_30d = 20
            signals.fb_group_intent_score = Decimal("0.8")
        elif "clothes" in product_lower:
            signals.fb_group_mentions_30d = 12
            signals.fb_group_intent_score = Decimal("0.65")
        elif "monitor" in product_lower:
            signals.fb_group_mentions_30d = 8
            signals.fb_group_intent_score = Decimal("0.5")
        else:
            signals.fb_group_mentions_30d = 5
            signals.fb_group_intent_score = Decimal("0.5")
            
        return signals

class RedditCollector(BaseCollector):
    """Collector for Reddit RSS (r/BabyBumps and related)."""
    
    def __init__(self, rate_limit_per_second: float = 0.5):
        super().__init__("reddit", rate_limit_per_second)
        self.logger = logger.bind(collector="reddit")
    
    async def collect(self, product_name: str, **kwargs) -> DemandSignals:
        """Collect demand signals from Reddit RSS (demo data for MVP)."""
        self.logger.info("Collecting Reddit signals (demo)", product=product_name)
        
        signals = DemandSignals()
        product_lower = product_name.lower()
        
        # Demo data for Reddit
        if "stroller" in product_lower:
            signals.fb_group_mentions_30d = 8  # repurposing field for Reddit mentions
            signals.fb_group_intent_score = Decimal("0.6")
        elif "car seat" in product_lower:
            signals.fb_group_mentions_30d = 12
            signals.fb_group_intent_score = Decimal("0.7")
        elif "toy" in product_lower:
            signals.fb_group_mentions_30d = 5
            signals.fb_group_intent_score = Decimal("0.4")
        elif "clothes" in product_lower:
            signals.fb_group_mentions_30d = 6
            signals.fb_group_intent_score = Decimal("0.5")
        elif "monitor" in product_lower:
            signals.fb_group_mentions_30d = 4
            signals.fb_group_intent_score = Decimal("0.4")
        else:
            signals.fb_group_mentions_30d = 3
            signals.fb_group_intent_score = Decimal("0.4")
            
        return signals

async def collect_multi_source_demand() -> dict:
    """Collect demand signals from multiple sources and return structured JSON."""
    products = [
        ("Baby Stroller", None, None, None),
        ("Car Seat", None, None, None),
        ("Baby Toy", None, None, None),
        ("Baby Clothes", None, None, None),
        ("Baby Monitor", None, None, None),
    ]
    
    results = {
        "scan_timestamp": datetime.now(timezone.utc).isoformat(),
        "sources": {},
        "aggregated_signals": {
            "total_mentions": 0,
            "sentiment_score": 0.0,
            "confidence": "LOW",
            "top_models": [],
            "recommendation": "WATCH"
        }
    }
    
    # Initialize collectors
    collectors = {
        "jiji": JijiCollector(),
        "facebook": FacebookCollector(),
        "instagram": InstagramPublicCollector(),
        "tiktok": TikTokPublicCollector(),
        "forum": ForumCollector(),
        "reddit": RedditCollector(),
    }
    
    # We'll collect signals for each product and then aggregate
    all_signals = {}
    for name, brand, model, category in products:
        signals = DemandSignals()
        source_status = {}
        
        # Run all collectors for this product
        for source_name, collector in collectors.items():
            try:
                collector_signals = await collector.collect(name, brand=brand, model=model, category=category)
                # Merge signals (non-None values overwrite)
                for field in collector_signals.__class__.model_fields:
                    if field not in ["entered_by", "entered_at"]:  # Skip metadata
                        value = getattr(collector_signals, field)
                        if value is not None:
                            setattr(signals, field, value)
                source_status[source_name] = "success"
            except Exception as e:
                logger.warning(f"Collector {source_name} failed for {name}", error=str(e))
                source_status[source_name] = f"failed: {str(e)}"
        
        all_signals[name] = {
            "signals": signals,
            "source_status": source_status
        }
        
        # Compose signal for this product
        try:
            product_signal = compose_signal(name, signals, brand=brand, model=model, category=category)
            # Store for aggregation
            # We'll aggregate later
        except Exception as e:
            logger.error(f"Failed to compose signal for {name}", error=str(e))
    
    # Build sources summary and aggregate
    total_mentions = 0
    sentiment_sum = Decimal("0")
    sentiment_count = 0
    product_scores = []
    
    for name, data in all_signals.items():
        signals = data["signals"]
        source_status = data["source_status"]
        
        # Count mentions from various fields
        mentions = 0
        if signals.jiji_active_listings is not None:
            mentions += signals.jiji_active_listings
        if signals.fb_group_mentions_30d is not None:
            mentions += signals.fb_group_mentions_30d
        if signals.ig_kenyan_mentions_30d is not None:
            mentions += signals.ig_kenyan_mentions_30d
        if signals.tiktok_kenyan_mentions_30d is not None:
            mentions += signals.tiktok_kenyan_mentions_30d
        
        total_mentions += mentions
        
        # Get sentiment score (average of intent scores)
        intent_scores = []
        if signals.fb_group_intent_score is not None:
            intent_scores.append(signals.fb_group_intent_score)
        # Note: we don't have a separate sentiment field, using intent score as proxy
        
        if intent_scores:
            avg_intent = sum(intent_scores) / len(intent_scores)
            sentiment_sum += avg_intent
            sentiment_count += 1
        
        # Compose signal to get demand score
        try:
            product_signal = compose_signal(name, signals)
            product_scores.append({
                "product": name,
                "score": float(product_signal.demand_score),
                "confidence": product_signal.confidence.value if hasattr(product_signal.confidence, 'value') else str(product_signal.confidence),
                "recommendation": product_signal.recommendation.value if hasattr(product_signal.recommendation, 'value') else str(product_signal.recommendation)
            })
        except Exception as e:
            logger.error(f"Failed to compose signal for {name} in aggregation", error=str(e))
    
    # Calculate overall sentiment score (0-1)
    overall_sentiment = float(sentiment_sum / sentiment_count) if sentiment_count > 0 else 0.5
    
    # Determine confidence based on number of successful sources
    # We'll hardcode for now
    confidence = "MEDIUM"
    
    # Determine overall recommendation based on average score
    avg_score = sum(p["score"] for p in product_scores) / len(product_scores) if product_scores else 0
    if avg_score >= 0.7:
        recommendation = "PURSUE"
    elif avg_score >= 0.4:
        recommendation = "WATCH"
    else:
        recommendation = "SKIP"
    
    # Top models (we don't have model-specific data, so leave empty)
    top_models = []
    
    results["sources"] = {
        # We'll simplify: just indicate which sources were attempted
        # In a real implementation, we'd have per-source signals
        "tiktok": {"status": "attempted"},
        "instagram": {"status": "attempted"},
        "forums": {"status": "attempted"},
        "marketplace": {"status": "attempted"},
        "reddit": {"status": "attempted"}
    }
    
    results["aggregated_signals"] = {
        "total_mentions": total_mentions,
        "sentiment_score": overall_sentiment,
        "confidence": confidence,
        "top_models": top_models,
        "recommendation": recommendation
    }
    
    # Also include per-product breakdown for readability
    results["products"] = product_scores
    
    return results

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
        print(f"Sentiment Score: {result['aggregated_signals']['sentiment_score']:.2f}")
        print("\nProduct Scores:")
        for product in result["products"]:
            print(f"  {product['product']}: {product['score']:.3f} ({product['recommendation']})")
        
    except Exception as e:
        logger.error("Failed to run multi-source demand collector", error=str(e))
        # Output error JSON
        error_result = {
            "error": str(e),
            "scan_timestamp": datetime.now(timezone.utc).isoformat()
        }
        print(json.dumps(error_result, indent=2))
        sys.exit(1)

if __name__ == "__main__":
    main()