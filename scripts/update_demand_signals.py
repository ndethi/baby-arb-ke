#!/usr/bin/env python3
"""
Update demand signal data by running all collectors.
"""
import asyncio
import json
import sys
from datetime import UTC, datetime

# Ensure we can import from the baby_arb package
sys.path.insert(0, './src')

from baby_arb.demand.aggregator import compose_signal
from baby_arb.demand.collect import collect_signals, default_collectors


async def main():
    # Load existing demand scout data
    with open('./data/cache/demand_scout/latest.json') as f:
        data = json.load(f)

    collectors = default_collectors()

    # Update each product. Every product's signals are replaced, so values
    # left over from earlier (demo) runs do not survive an update.
    for product in data['products']:
        product_name = product['name']
        brand = product.get('brand')
        model = product.get('model')
        category = product.get('category')

        combined_signals = await collect_signals(
            product_name, collectors, brand=brand, model=model, category=category
        )

        # Compose the product signal to get demand_score and confidence
        product_signal = compose_signal(
            name=product_name,
            signals=combined_signals,
            brand=brand,
            model=model,
            category=category,
        )

        # Update the product in the data
        unknown = product_signal.confidence == "UNKNOWN"
        product['demand_score'] = None if unknown else float(product_signal.demand_score)
        product['confidence'] = product_signal.confidence
        product['recommendation'] = product_signal.recommendation
        product['signals'] = combined_signals.model_dump()

    # Update scan timestamp
    data['scan_timestamp'] = datetime.now(UTC).isoformat()

    # Save updated data
    with open('./data/cache/demand_scout/latest.json', 'w') as f:
        json.dump(data, f, indent=2, default=str)

    print("Successfully updated demand scout data")


if __name__ == '__main__':
    asyncio.run(main())