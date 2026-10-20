#!/usr/bin/env python3
"""
Update demand signal data by running all collectors.
"""
import asyncio
import json
import sys
from datetime import datetime, timezone
from decimal import Decimal

# Ensure we can import from the baby_arb package
sys.path.insert(0, './src')

from baby_arb.demand.collectors.jiji import JijiCollector
from baby_arb.demand.collectors.facebook import FacebookCollector
from baby_arb.demand.collectors.instagram_public import InstagramPublicCollector
from baby_arb.demand.collectors.tiktok_public import TikTokPublicCollector
from baby_arb.demand.aggregator import compose_signal
from baby_arb.models.demand import DemandSignals


async def main():
    # Load existing demand scout data
    with open('./data/cache/demand_scout/latest.json', 'r') as f:
        data = json.load(f)

    # Initialize collectors
    collectors = [
        JijiCollector(),
        FacebookCollector(),
        InstagramPublicCollector(),
        TikTokPublicCollector(),
    ]

    # Update each product
    for product in data['products']:
        product_name = product['name']
        brand = product.get('brand')
        model = product.get('model')
        category = product.get('category')

        # Start with an empty DemandSignals object
        combined_signals = DemandSignals()

        # Run each collector and update combined_signals with non-null values
        for collector in collectors:
            try:
                signals = await collector.collect(product_name)
                # Update fields that are not None
                for field in signals.model_fields:
                    value = getattr(signals, field)
                    if value is not None:
                        setattr(combined_signals, field, value)
            except Exception as e:
                print(f"Error running {collector.__class__.__name__} for {product_name}: {e}")
                # Continue with other collectors

        # Compose the product signal to get demand_score and confidence
        product_signal = compose_signal(
            name=product_name,
            signals=combined_signals,
            brand=brand,
            model=model,
            category=category,
        )

        # Update the product in the data
        product['demand_score'] = float(product_signal.demand_score)
        product['confidence'] = product_signal.confidence
        product['signals'] = combined_signals.model_dump()

    # Update scan timestamp
    data['scan_timestamp'] = datetime.now(timezone.utc).isoformat()

    # Save updated data
    with open('./data/cache/demand_scout/latest.json', 'w') as f:
        json.dump(data, f, indent=2, default=str)

    print("Successfully updated demand scout data")


if __name__ == '__main__':
    asyncio.run(main())