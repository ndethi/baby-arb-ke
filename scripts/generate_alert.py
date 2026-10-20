#!/usr/bin/env python3
"""
Generate a daily Telegram alert with high-signal purchase opportunities and demand generation ideas for baby-arb-ke
"""

import json
import os
import sys
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path

# Add the project root to sys.path to import config if needed
sys.path.append(str(Path(__file__).parent.parent))

def load_target_categories():
    """Load target categories from config/target_categories.yaml or use defaults."""
    config_path = Path(__file__).parent.parent / "config" / "target_categories.yaml"
    default_categories = ["car seat", "stroller", "nursery", "feeding"]
    if config_path.exists():
        try:
            import yaml
            with open(config_path) as f:
                data = yaml.safe_load(f)
                # Expecting a list of strings
                if isinstance(data, list):
                    return [str(item).strip().lower() for item in data]
        except Exception as e:
            print(f"Warning: Could not load target categories from {config_path}: {e}", file=sys.stderr)
    return default_categories

def demand_scout_file_is_fresh(filepath, max_age_days=2):
    """Check if the demand scout JSON is less than max_age_days old."""
    if not os.path.exists(filepath):
        return False
    mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
    return datetime.now() - mtime < timedelta(days=max_age_days)

def main():
    demand_scout_path = Path(__file__).parent.parent / "data" / "cache" / "demand_scout" / "latest.json"
    
    if not demand_scout_file_is_fresh(demand_scout_path):
        print(f"Warning: Demand scout file {demand_scout_path} is older than 2 days or missing. Using anyway.", file=sys.stderr)
    
    try:
        with open(demand_scout_path) as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error: Could not load demand scout file {demand_scout_path}: {e}", file=sys.stderr)
        sys.exit(1)
    
    products = data.get("products", [])
    generated_at = data.get("generated_at", datetime.now().isoformat())
    
    # Target categories
    target_categories = load_target_categories()
    
    # Fallback FX rate
    FX_RATE = 145.5  # KES per USD
    
    # Prepare high-signal items
    high_signal_items = []
    represented_categories = set()
    
    for product in products:
        demand_score = product.get("demand_score", 0.0)
        confidence = product.get("confidence", "").upper()
        if demand_score >= 0.6 and confidence in ("HIGH", "MEDIUM"):
            name = product.get("name", "Unknown Product")
            brand = product.get("brand", "")
            model = product.get("model", "")
            category = product.get("category", "").replace("_", " ").lower()
            # Use name as the primary product identifier; it already includes brand/model in the data
            display_name = name
            signals = product.get("signals", {})
            jiji_median_sold_kes = signals.get("jiji_median_sold_kes")
            
            if jiji_median_sold_kes is None:
                # Skip if we don't have a reference KE price
                continue
            
            # Compute target landed cost (USD) and target KE price (KES) for 50% gross margin
            # sale_price = cost * 1.5  => cost = sale_price / 1.5
            target_ke_price_kes = float(jiji_median_sold_kes)
            target_landed_cost_usd = (target_ke_price_kes / 1.5) / FX_RATE
            
            # Compliance flags (simplified)
            compliance_flags = []
            if "car seat" in category:
                compliance_flags.append("car-seat-DOM")
            # Add more compliance rules as needed
            
            # Source markets (we assume all are available if we have the product)
            source_markets = ["eBay", "Mercari", "FB", "OfferUp"]
            
            # Build search URLs (URL encode the product name)
            query = urllib.parse.quote_plus(name.strip())
            urls = {
                "eBay": f"https://www.ebay.com/sch/i.html?_nkw={query}",
                "Mercari": f"https://www.mercari.com/search/?keyword={query}",
                "FB Marketplace": f"https://www.facebook.com/marketplace/search/?query={query}",
                "OfferUp": f"https://offerup.com/search/?q={query}"
            }
            
            high_signal_items.append({
                "name": name,
                "brand": brand,
                "model": model,
                "category": category,
                "demand_score": demand_score,
                "confidence": confidence,
                "target_landed_cost_usd": target_landed_cost_usd,
                "target_ke_price_kes": target_ke_price_kes,
                "compliance_flags": compliance_flags,
                "source_markets": source_markets,
                "urls": urls,
                "display_name": name  # Store the display name for printing
            })
            
            represented_categories.add(category)
    
    # Prepare demand generation ideas: categories in target but not represented
    demand_ideas = []
    for cat in target_categories:
        if cat not in represented_categories:
            # Provide a generic idea block
            reason = "No recent listings in demand scout (score < 0.2)"
            ideas = []
            if "nursery" in cat:
                ideas = [
                    "Run a TikTok #KenyanNurseryDecor challenge",
                    "Partner with local maternity hospitals for product seeding",
                    "Create Instagram reels showing “room transformation” with KE‑priced blankets"
                ]
            elif "feeding" in cat:
                ideas = [
                    "Sponsor a mom‑group Facebook Live demo",
                    "Create comparative reels “US vs KE baby bottle prices”",
                    "Offer a limited‑time discount code for first 50 buyers"
                ]
            elif "car seat" in cat:
                ideas = [
                    "Run a TikTok #CarSeatSafetyKE challenge with local influencers",
                    "Partner with driving schools for product seeding",
                    "Create Instagram carousels showing correct installation"
                ]
            elif "stroller" in cat:
                ideas = [
                    "Run a TikTok #StrollerStrollKE challenge in Nairobi parks",
                    "Partner with mommy-and-me fitness groups",
                    "Create reels showing “stroller hacks” for Nairobi traffic"
                ]
            else:
                ideas = [
                    f"Create TikTok content showcasing {cat} products",
                    f"Partner with local parenting influencers for {cat}",
                    f"Run a Facebook Live demo for {cat} products"
                ]
            
            demand_ideas.append({
                "category": cat,
                "reason": reason,
                "ideas": ideas
            })
    
    # Build the message
    lines = []
    # Header
    date_str = None
    # Try to use scan_timestamp first (updated by update script)
    if isinstance(data.get('scan_timestamp'), str):
        try:
            dt = datetime.fromisoformat(data['scan_timestamp'].replace('Z', '+00:00'))
            date_str = dt.strftime('%Y-%m-%d')
        except Exception:
            pass
    # Fallback to generated_at
    if date_str is None and isinstance(data.get('generated_at'), str):
        try:
            dt = datetime.fromisoformat(data['generated_at'].replace('Z', '+00:00'))
            date_str = dt.strftime('%Y-%m-%d')
        except Exception:
            pass
    # Fallback to current date
    if date_str is None:
        date_str = datetime.now().strftime('%Y-%m-%d')
    
    lines.append(f"🗓️ {date_str} Daily Baby‑Arb‑Ke Alert")
    lines.append("")
    # High Signal Purchases Available
    if high_signal_items:
        lines.append("🟢 HIGH SIGNAL PURCHASES AVAILABLE")
        for idx, item in enumerate(high_signal_items, start=1):
            lines.append(f"{idx}. {item['display_name']}")
            lines.append(f"   Demand score: {item['demand_score']:.2f} ({item['confidence']})")
            lines.append(f"   Target landed cost: ${item['target_landed_cost_usd']:.2f} → Target KE price: KES {item['target_ke_price_kes']:,.0f}")
            if item['compliance_flags']:
                lines.append(f"   Compliance: {', '.join(item['compliance_flags'])}")
            lines.append(f"   Sources: {', '.join(item['source_markets'])}")
            for market, url in item['urls'].items():
                lines.append(f"   🔗 {market}: {url}")
            lines.append("")
    else:
        lines.append("🟢 HIGH SIGNAL PURCHASES AVAILABLE")
        lines.append("   No high‑signal items meeting the threshold (score >= 0.6, confidence HIGH/MEDIUM).")
        lines.append("")
    
    # Demand Generation Ideas
    if demand_ideas:
        lines.append("🟡 DEMAND GENERATION IDEAS")
        for idea in demand_ideas:
            lines.append(f"• {idea['category'].title()}")
            lines.append(f"   Reason: {idea['reason']}")
            lines.append("   Ideas: " + "; ".join(idea['ideas']))
            lines.append("")
    else:
        lines.append("🟡 DEMAND GENERATION IDEAS")
        lines.append("   All target categories are currently represented in high‑signal items.")
        lines.append("")
    
    lines.append("*Generated by Hermes Agent – daily-demand-alert skill*")
    
    message = "\n".join(lines)
    print(message)

if __name__ == "__main__":
    main()