#!/usr/bin/env python3
"""
Sourcing script for baby-arb-ke project.
Uses browser tools to search US marketplaces for priority items from the sourcing brief.
"""

import json
import re
from datetime import datetime
from pathlib import Path
from decimal import Decimal

# We'll use the browser tools via Hermes agent interface
# For now, we'll simulate the search by showing what we would do
# In a real implementation, we'd call browser_navigate, browser_type, etc.

def calculate_shipping_cost_estimate(weight_lbs=5):
    """
    Estimate shipping cost from US warehouse to Nairobi via consolidator.
    Based on AGENTS.md: $25-35 per item via consolidator.
    We'll use a base rate + per lb rate for simplicity.
    """
    base_rate = 25.0  # Minimum from AGENTS.md
    per_lb_rate = 2.0  # Estimated
    return base_rate + (weight_lbs * per_lb_rate)

def search_ebay_for_item(query, max_results=10):
    """
    Simulate searching eBay for an item.
    In a real implementation, this would use:
    - browser_navigate to eBay.com
    - browser_type to enter query in search box
    - browser_press Enter
    - browser_snapshot to get results
    - Extract listings with browser_vision or parsing
    
    For now, we'll return mock data to demonstrate the flow.
    """
    print(f"[SEARCH] Would search eBay for: '{query}'")
    print(f"[SEARCH] Would navigate to eBay.com, enter query, and extract results")
    
    # Mock results - in reality these would come from actual scraping
    mock_results = [
        {
            "title": f"{query} - Like New",
            "price": 80.00,
            "shipping": 15.00,
            "condition": "Like New",
            "location": "US",
            "url": f"https://ebay.com/itm/{hash(query) % 1000000}",
            "seller_rating": 4.8,
            "reviews": 1242
        },
        {
            "title": f"{query} - Excellent Condition",
            "price": 95.00,
            "shipping": 0.00,  # Free shipping
            "condition": "Excellent",
            "location": "US",
            "url": f"https://ebay.com/itm/{hash(query) % 1000000 + 1}",
            "seller_rating": 4.9,
            "reviews": 856
        },
        {
            "title": f"{query} - Used - Good",
            "price": 65.00,
            "shipping": 12.00,
            "condition": "Good",
            "location": "US",
            "url": f"https://ebay.com/itm/{hash(query) % 1000000 + 2}",
            "seller_rating": 4.6,
            "reviews": 2109
        }
    ]
    
    return mock_results[:max_results]

def filter_and_rank_results(results, max_price_usd, min_condition="Like New"):
    """
    Filter and rank search results based on:
    - Price (under max_price_usd)
    - Condition (prefer Like New, Excellent, etc.)
    - Seller rating
    - Shipping cost
    """
    # Condition ranking (higher is better)
    condition_rank = {
        "Like New": 3,
        "Excellent": 3,
        "Very Good": 2,
        "Good": 1,
        "Acceptable": 0
    }
    
    filtered = []
    for item in results:
        # Check price (item price + shipping)
        total_cost = item["price"] + item["shipping"]
        if total_cost > max_price_usd:
            continue
            
        # Check condition
        condition_score = condition_rank.get(item["condition"], 0)
        if condition_score < condition_rank.get(min_condition, 0):
            continue
            
        # Calculate score (condition weight 40%, price weight 30%, seller rating 30%)
        price_score = 1.0 - (total_cost / max_price_usd)  # Lower price = higher score
        seller_score = item["seller_rating"] / 5.0
        condition_score_norm = condition_score / 3.0
        
        total_score = (condition_score_norm * 0.4) + (price_score * 0.3) + (seller_score * 0.3)
        
        filtered.append({
            **item,
            "total_cost": total_cost,
            "score": total_score
        })
    
    # Sort by score descending
    filtered.sort(key=lambda x: x["score"], reverse=True)
    return filtered

def calculate_landed_cost(usd_price, shipping_usd, weight_lbs=5):
    """
    Calculate total landed cost in USD including:
    - Item price
    - US shipping
    - International shipping to Nairobi (via consolidator)
    - Handling fees
    """
    us_shipping = shipping_usd
    intl_shipping = calculate_shipping_cost_estimate(weight_lbs)
    handling_fee = 5.0  # Estimated handling fee
    
    total_usd = usd_price + us_shipping + intl_shipping + handling_fee
    return total_usd

def format_currency_usd(amount):
    """Format amount as USD currency."""
    return f"${amount:.2f}"

def format_currency_kes(amount):
    """Format amount as KES currency using ~145 exchange rate."""
    kes_amount = amount * 145
    return f"KES {kes_amount:,.0f}"

def source_priority_items(brief_data, warehouse_address):
    """
    Main function to source priority items from the brief.
    """
    print(f"🔍 Sourcing Priority Items for Warehouse: {warehouse_address}")
    print("=" * 60)
    
    # Parse the brief data to extract priority items
    # For now, we'll extract from the brief file directly
    brief_path = Path("/Users/ndethi/dev/ir/baby-arb-ke/docs/progress/sourcing_brief_2026-05-18.md")
    
    if not brief_path.exists():
        print("❌ Brief file not found!")
        return
    
    brief_content = brief_path.read_text()
    
    # Extract priority items (simple parsing for demo)
    # In reality, we'd parse the structured brief or pass data directly
    # Based on the updated brief with 4 product types
    priority_items = [
        {
            "product": "NUNA PIPA Lite RX",
            "brand": "NUNA",
            "model": "PIPA Lite RX",
            "target_landed_cost_usd": Decimal("112.07"),
            "target_ke_sale_price_kes": Decimal("32500"),
            "max_price_usd": float(Decimal("112.07")),  # We'll use target as max for now
            "condition": "like-new | any-functional",
            "compliance_flags": ["car-seat-DOM"],
            "search_queries": [
                "NUNA PIPA Lite RX",
                "NUNA PIPA Lite RX used",
                "NUNA PIPA Lite RX 2022"
            ]
        },
        {
            "product": "Medela Pump in Style Advanced",
            "brand": "Medela",
            "model": "Pump in Style Advanced",
            "target_landed_cost_usd": Decimal("62.07"),
            "target_ke_sale_price_kes": Decimal("18000"),
            "max_price_usd": float(Decimal("62.07")),
            "condition": "any-functional",
            "compliance_flags": [],
            "search_queries": [
                "Medela Pump in Style Advanced",
                "Medela Pump in Style Advanced used",
                "Medela Pump in Style Advanced 2022"
            ]
        },
        {
            "product": "DaVinci Jenny Lind",
            "brand": "DaVinci",
            "model": "Jenny Lind",
            "target_landed_cost_usd": Decimal("96.55"),
            "target_ke_sale_price_kes": Decimal("28000"),
            "max_price_usd": float(Decimal("96.55")),
            "condition": "any-functional",
            "compliance_flags": [],
            "search_queries": [
                "DaVinci Jenny Lind",
                "DaVinci Jenny Lind used",
                "DaVinci Jenny Lind 2022"
            ]
        },
        {
            "product": "BOB Revolution Flex 3.0 Duallie",
            "brand": "BOB",
            "model": "Revolution Flex 3.0 Duallie",
            "target_landed_cost_usd": Decimal("155.17"),
            "target_ke_sale_price_kes": Decimal("45000"),
            "max_price_usd": float(Decimal("155.17")),
            "condition": "gently-used | any-functional",
            "compliance_flags": [],
            "search_queries": [
                "BOB Revolution Flex 3.0 Duallie",
                "BOB Revolution Flex 3.0 Duallie used",
                "BOB Revolution Flex 3.0 Duallie 2022"
            ]
        }
    ]
    
    results = []
    
    for item in priority_items:
        print(f"\n📦 Sourcing: {item['product']}")
        print(f"   Target landed cost: {format_currency_usd(item['target_landed_cost_usd'])}")
        print(f"   Target resale price: {format_currency_kes(item['target_ke_sale_price_kes'])}")
        print(f"   Max US budget: {format_currency_usd(item['max_price_usd'])}")
        print(f"   Condition: {item['condition']}")
        if item['compliance_flags']:
            print(f"   Compliance: {', '.join(item['compliance_flags'])}")
        
        item_results = []
        
        # Search using each query
        for query in item['search_queries']:
            print(f"   🔎 Searching: '{query}'")
            raw_results = search_ebay_for_item(query, max_results=5)
            
            # Filter and rank
            filtered = filter_and_rank_results(
                raw_results, 
                max_price_usd=item['max_price_usd'],
                min_condition="Like New" if "like-new" in item['condition'] else "Good"
            )
            
            # Add to item results (avoid duplicates by URL)
            seen_urls = set()
            for result in filtered:
                if result['url'] not in seen_urls:
                    seen_urls.add(result['url'])
                    item_results.append(result)
        
        # Sort all results for this item by score
        item_results.sort(key=lambda x: x['score'], reverse=True)
        
        # Take top 3 for this item
        top_results = item_results[:3]
        
        if top_results:
            print(f"   ✅ Found {len(top_results)} viable options:")
            for i, result in enumerate(top_results, 1):
                # Determine weight based on product type
                weight_lbs = 5  # Default
                if "car seat" in item['product'].lower() or "pump" in item['product'].lower():
                    weight_lbs = 5
                elif "crib" in item['product'].lower() or "jenny lind" in item['product'].lower():
                    weight_lbs = 25  # Cribs are heavier
                elif "stroller" in item['product'].lower() or "bob" in item['product'].lower():
                    weight_lbs = 15  # Strollers medium weight
                
                landed_cost = calculate_landed_cost(
                    result['price'], 
                    result['shipping'],
                    weight_lbs=weight_lbs
                )
                
                # Calculate potential margin
                target_ke_sale = float(item['target_ke_sale_price_kes']) / 145.0  # Convert KES to USD
                margin = ((target_ke_sale - landed_cost) / target_ke_sale) * 100 if target_ke_sale > 0 else 0
                
                print(f"      {i}. {result['title']}")
                print(f"         Price: {format_currency_usd(result['price'])} + shipping {format_currency_usd(result['shipping'])} = {format_currency_usd(result['price'] + result['shipping'])}")
                print(f"         Landed cost (US+Intl+Handling): {format_currency_usd(landed_cost)}")
                print(f"         Condition: {result['condition']} | Seller: {result['seller_rating']}★ ({result['reviews']} reviews)")
                print(f"         URL: {result['url']}")
                print(f"         Potential margin: {margin:.1f}% (target: {format_currency_kes(item['target_ke_sale_price_kes'])})")
                print()
                
                results.append({
                    "item": item,
                    "result": result,
                    "landed_cost_usd": landed_cost,
                    "potential_margin_percent": margin
                })
        else:
            print(f"   ❌ No viable options found under budget")
    
    return results

def generate_sourcing_report(results, warehouse_address):
    """
    Generate a sourcing report with recommended buys.
    """
    print("\n" + "=" * 60)
    print("📋 SOURCING RECOMMENDATIONS REPORT")
    print("=" * 60)
    print(f"Warehouse: {warehouse_address}")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    if not results:
        print("❌ No items sourced successfully.")
        return
    
    # Group by item
    by_item = {}
    for result in results:
        item_name = result['item']['product']
        if item_name not in by_item:
            by_item[item_name] = []
        by_item[item_name].append(result)
    
    total_potential_profit = 0
    
    for item_name, item_results in by_item.items():
        print(f"🛒 {item_name}")
        print("-" * 40)
        
        # Show best option
        best = item_results[0]
        item_data = best['item']
        result_data = best['result']
        
        target_ke_sale = float(item_data['target_ke_sale_price_kes']) / 145.0
        profit_usd = target_ke_sale - best['landed_cost_usd']
        profit_kes = profit_usd * 145
        margin_percent = (profit_usd / target_ke_sale) * 100 if target_ke_sale > 0 else 0
        
        total_potential_profit += profit_usd
        
        print(f"   🏆 RECOMMENDED: {result_data['title']}")
        print(f"   💰 Cost breakdown:")
        print(f"      Item price: {format_currency_usd(result_data['price'])}")
        print(f"      US shipping: {format_currency_usd(result_data['shipping'])}")
        print(f"      Intl shipping: {format_currency_usd(calculate_shipping_cost_estimate())}")
        print(f"      Handling: {format_currency_usd(5.00)}")
        print(f"      → Total landed: {format_currency_usd(best['landed_cost_usd'])}")
        print(f"   💵 Revenue potential:")
        print(f"      Target sale: {format_currency_kes(item_data['target_ke_sale_price_kes'])} (~{format_currency_usd(target_ke_sale)} USD)")
        print(f"      Profit: {format_currency_kes(profit_kes)} (~{format_currency_usd(profit_usd)} USD)")
        print(f"      Margin: {margin_percent:.1f}%")
        print(f"   🔗 Purchase link: {result_data['url']}")
        print()
    
    print(f"💰 TOTAL ESTIMATED PROFIT: {format_currency_kes(total_potential_profit * 145)} (~{format_currency_usd(total_potential_profit)} USD)")
    print(f"📊 Based on {len(results)} sourced items")
    print()
    print("⚠️  NEXT STEPS:")
    print("   1. Review recommended items above")
    print("   2. Verify condition and compliance manually")
    print("   3. For items >$200, seek Telegram approval (per AGENTS.md)")
    print("   4. Execute purchase using virtual card")
    print("   5. Ship to warehouse for consolidation")
    print("   6. List on Jiji/storefront at target price")

def main():
    """
    Main execution function.
    """
    warehouse_address = "4124 Sunset Trail, Brooklyn Park, MN 55443"
    
    print("🚀 Baby-Arb-Ke Sourcing Assistant")
    print("🎯 Finding best deals on high-demand baby items")
    print()
    
    # Source priority items from the brief
    results = source_priority_items(None, warehouse_address)
    
    # Generate report
    generate_sourcing_report(results, warehouse_address)
    
    # Save results to file for future reference
    output_path = Path("/Users/ndethi/dev/ir/baby-arb-ke/data/cache/sourcing_results_latest.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Convert results to JSON-serializable format
    json_results = []
    for result in results:
        json_results.append({
            "item": {
                "product": result['item']['product'],
                "brand": result['item']['brand'],
                "model": result['item']['model'],
                "target_landed_cost_usd": float(result['item']['target_landed_cost_usd']),
                "target_ke_sale_price_kes": float(result['item']['target_ke_sale_price_kes'])
            },
            "result": {
                "title": result['result']['title'],
                "price": result['result']['price'],
                "shipping": result['result']['shipping'],
                "condition": result['result']['condition'],
                "url": result['result']['url'],
                "seller_rating": result['result']['seller_rating'],
                "reviews": result['result']['reviews']
            },
            "landed_cost_usd": result['landed_cost_usd'],
            "potential_margin_percent": result['potential_margin_percent']
        })
    
    with open(output_path, 'w') as f:
        json.dump(json_results, f, indent=2)
    
    print(f"💾 Detailed results saved to: {output_path}")

if __name__ == "__main__":
    main()