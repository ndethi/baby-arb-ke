#!/usr/bin/env python3
"""
Aggregator for baby-arb-ke: combines pump, stroller, and toy trackers,
weights them (pumps heavy, then stroller/toys), calculates margin potential,
and outputs top N items with purchase links.

Assumes tracker CSVs have columns:
timestamp,model,price_usd,source,link,tier,demand_score
"""

import csv
import os
from datetime import datetime
from decimal import Decimal
import json

# ---- Configuration ----
PUMP_WEIGHT = 0.5
STROLLER_WEIGHT = 0.3
TOY_WEIGHT = 0.2
MARGIN_FLOOR_PCT = 0.50  # 50% gross margin minimum
TOP_N = 10  # changed from 5 to 10

# No KE resale price is invented from the US price. Until a sourced KE
# reference price exists (Jiji snapshots, docs/live_scraping_plan.md Phase 2)
# every item abstains. When it does, margin must come from
# baby_arb.pricing.calculate_landed_cost, not a per-kg guess.
NO_KE_PRICE_REASON = (
    "no sourced KE resale price (Jiji snapshots not built, "
    "docs/live_scraping_plan.md Phase 2)"
)


def ke_reference_price_usd(tracker_type, model):
    """Return a sourced KE resale price in USD, or None when there is none.

    No KE price source exists yet, so this always returns None.
    """
    return None


def read_tracker(tracker_type):
    """
    Read the latest entries from a tracker CSV.
    Returns list of dicts with normalized keys.
    """
    path_map = {
        'pump': 'data/tracker/pump_tracker.csv',
        'stroller': 'data/tracker/stroller_tracker.csv',
        'toy': 'data/tracker/toy_tracker.csv',
    }
    path = path_map[tracker_type]
    if not os.path.exists(path):
        print(f"⚠️  Tracker file not found: {path}")
        return []
    
    rows = []
    with open(path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Ensure numeric fields are proper types
            try:
                row['price_usd'] = float(row['price_usd'])
                row['demand_score'] = float(row['demand_score'])
            except (ValueError, KeyError):
                # skip malformed rows
                continue
            rows.append(row)
    return rows

def process_items():
    """Read all trackers and rank items that have a sourced KE price.

    Returns:
        (ranked, abstained): ranked items meeting the margin floor, and
        items skipped as UNKNOWN with a reason.
    """
    ranked = []
    abstained = []

    for tracker_type in ['pump', 'stroller', 'toy']:
        for row in read_tracker(tracker_type):
            price_usd = row['price_usd']
            if price_usd is None or price_usd <= 0:
                continue

            resale_usd = ke_reference_price_usd(tracker_type, row['model'])
            if resale_usd is None:
                abstained.append({
                    'tracker_type': tracker_type,
                    'model': row['model'],
                    'price_usd': price_usd,
                    'reason': NO_KE_PRICE_REASON,
                })
                continue

            # Unreachable until a KE price source exists; margin must then be
            # computed with the pricing engine (landed cost, duty, FX), which
            # needs per-listing weight and dimensions the tracker does not have.
            raise NotImplementedError("wire margin to baby_arb.pricing before enabling KE prices")

    ranked.sort(key=lambda x: x['effective_score'], reverse=True)
    return ranked[:TOP_N], abstained

def main():
    print(f"🕒 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} Aggregator: Top {TOP_N} Items by Weighted Score")
    print("=" * 80)
    
    topN, abstained = process_items()

    if not topN:
        print("❌ No items ranked: margin cannot be computed without a KE resale price.")
        if abstained:
            print(f"   UNKNOWN: {len(abstained)} tracker items skipped ({abstained[0]['reason']}).")
        else:
            print("   No tracker rows found.")
        return

    # Print header
    print(f"{'Rank':<4} {'Type':<8} {'Model':<25} {'Price US$':<10} {'Margin %':<8} {'Est. Resale US$':<12} {'Source':<10} {'Link'}")
    print("-" * 80)
    
    for i, item in enumerate(topN, 1):
        # Display full link for clickability
        link_disp = item['link']
        print(f"{i:<4} {item['tracker_type']:<8} {item['model']:<25} "
              f"${item['price_usd']:<9.2f} {item['margin_pct']:<7.1f}% "
              f"${item['resale_price_usd']:<11.2f} {item['source']:<10} {link_disp}")
    
    print("\n💡 Notes:")
    print(f"   - Weights: pumps={PUMP_WEIGHT}, strollers={STROLLER_WEIGHT}, toys={TOY_WEIGHT}")
    print(f"   - Margin floor: {MARGIN_FLOOR_PCT*100}%")
    print(f"   - Links are direct to the marketplace listing (eBay, Mercari, FB, OfferUp)")

if __name__ == "__main__":
    main()
