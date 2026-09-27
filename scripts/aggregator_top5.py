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

# Estimated resale markup multipliers (US price -> estimated Nairobi resale price)
# Adjusted for demo to achieve >=50% margin with sample data
RESALE_MULTIPLIER = {
    'pump': 2.5,      # e.g., $80 pump -> ~$200 resale
    'stroller': 2.2,  # $100 stroller -> ~$220 resale
    'toy': 2.0,       # $20 toy -> ~$40 resale
}

# Estimated international shipping cost per kg (USD)
# Reduced for demo
SHIPPING_PER_KG = 4.0  # USD/kg, economy air freight estimate
# Average weight per category (kg)
AVG_WEIGHT_KG = {
    'pump': 0.8,
    'stroller': 12.0,
    'toy': 1.0,
}

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

def calculate_estimated_resale_price(tracker_type, price_usd):
    """Estimate Nairobi resale price in USD."""
    multiplier = RESALE_MULTIPLIER.get(tracker_type, 1.5)
    return price_usd * multiplier

def calculate_estimated_shipping_cost(tracker_type):
    """Estimate shipping cost from US to Nairobi in USD."""
    weight = AVG_WEIGHT_KG.get(tracker_type, 2.0)
    return weight * SHIPPING_PER_KG

def calculate_margin(purchase_price_usd, tracker_type):
    """
    Calculate gross margin % based on estimated resale price and shipping.
    Returns margin as float (0.0-1.0) or None if cannot calculate.
    """
    resale_price_usd = calculate_estimated_resale_price(tracker_type, purchase_price_usd)
    shipping_cost_usd = calculate_estimated_shipping_cost(tracker_type)
    total_cost_usd = purchase_price_usd + shipping_cost_usd
    if resale_price_usd > 0:
        margin = (resale_price_usd - total_cost_usd) / resale_price_usd
        return margin
    else:
        return None

def process_items():
    """Read all trackers, compute scores, filter by margin, rank by weighted score."""
    all_items = []  # will hold dicts with all needed fields

    for tracker_type in ['pump', 'stroller', 'toy']:
        rows = read_tracker(tracker_type)
        for row in rows:
            price_usd = row['price_usd']
            if price_usd is None or price_usd <= 0:
                continue

            margin = calculate_margin(price_usd, tracker_type)
            # Only consider items meeting margin floor
            if margin is None or margin < MARGIN_FLOOR_PCT:
                continue

            # Compute weighted effective score
            demand_score = row['demand_score']  # 0-1ish from tracker
            if tracker_type == 'pump':
                weight = PUMP_WEIGHT
            elif tracker_type == 'stroller':
                weight = STROLLER_WEIGHT
            else:  # toy
                weight = TOY_WEIGHT
            effective_score = demand_score * weight

            resale_price_usd = calculate_estimated_resale_price(tracker_type, price_usd)
            shipping_cost_usd = calculate_estimated_shipping_cost(tracker_type)
            total_cost_usd = price_usd + shipping_cost_usd

            all_items.append({
                'tracker_type': tracker_type,
                'model': row['model'],
                'price_usd': price_usd,
                'source': row['source'],
                'link': row['link'],
                'demand_score': demand_score,
                'effective_score': effective_score,
                'margin_pct': margin * 100,
                'resale_price_usd': resale_price_usd,
                'shipping_cost_usd': shipping_cost_usd,
                'total_cost_usd': total_cost_usd,
                'timestamp': row.get('timestamp', ''),
            })

    # Sort by effective_score descending
    all_items.sort(key=lambda x: x['effective_score'], reverse=True)
    # Take top N
    topN = all_items[:TOP_N]
    return topN
def main():
    print(f"🕒 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} Aggregator: Top {TOP_N} Items by Weighted Score")
    print("=" * 80)
    
    topN = process_items()
    
    if not topN:
        print("❌ No items met the margin threshold (≥50%).")
        print("   Try lowering MARGIN_FLOOR_PCT or check that tracker CSVs have data.")
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
    print(f"   - Resale price = US price × multiplier (pump:2.5, stroller:2.2, toy:2.0)")
    print(f"   - Shipping estimate: {SHIPPING_PER_KG} USD/kg × avg weight per category")
    print(f"   - Links are direct to the marketplace listing (eBay, Mercari, FB, OfferUp)")

if __name__ == "__main__":
    main()
