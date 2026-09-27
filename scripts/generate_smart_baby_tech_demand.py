#!/usr/bin/env python3
"""
Smart Baby Tech Demand Generation Script for baby-arb-ke.

Creates and executes demand generation campaigns for emerging smart baby tech
products (Owlet, Nanit, smart monitors) targeting the Kenyan market through
content marketing, social media tracking, and marketplace demand monitoring.

This script handles:
1. Social listening for smart baby tech mentions
2. Content opportunity identification
3. Marketplace demand monitoring
4. Influencer outreach tracking
5. Campaign performance reporting
"""

import json
import os
import csv
from datetime import datetime
from urllib.parse import quote_plus
import requests
import structlog

logger = structlog.get_logger()

# Load configuration
def load_yaml_config(path, default):
    """Load a YAML config file; if missing or invalid, return default."""
    try:
        import yaml
        if os.path.exists(path):
            with open(path, 'r') as f:
                return yaml.safe_load(f)
    except Exception:
        pass
    return default

def ensure_dir(path):
    """Ensure directory exists."""
    os.makedirs(path, exist_ok=True)

# Target smart baby tech products
SMART_BABY_TECH_PRODUCTS = {
    "Owlet Smart Sock": {
        "description": "Baby breathing/heart rate monitor sock",
        "pain_points": ["SIDS anxiety", "sleep tracking", "peace of mind"],
        "content_angles": ["How Owlet gives peace of mind", "Sleep tracking for new parents", "Is smart monitoring worth it?"],
        "price_range_usd": "$150-250",
        "influencer_multiplier": 1.2
    },
    "Nanit Smart Camera": {
        "description": "Sleep tracking smart camera monitor",
        "pain_points": ["Nap tracking", "room monitoring", "split shift parenting"],
        "content_angles": ["Track baby's sleep from anywhere", "Smart nursery setup", "Camera vs sock monitor"],
        "price_range_usd": "$200-300",
        "influencer_multiplier": 1.0
    },
    "Smart Video Monitor": {
        "description": "WiFi-enabled video baby monitor",
        "pain_points": ["Remote monitoring", "two-way talk", "night vision"],
        "content_angles": ["Best video monitors for working parents", "WiFi monitor setup guide", "Monitor comparison"],
        "price_range_usd": "$100-200",
        "influencer_multiplier": 1.1
    },
    "Smart Thermometer": {
        "description": "Connected thermometer with app tracking",
        "pain_points": ["Fever tracking", "medication reminders", "doctor visits"],
        "content_angles": ["Track fevers smart", "When to worry about fever", "Smart health tracking"],
        "price_range_usd": "$40-80",
        "influencer_multiplier": 0.9
    }
}

def collect_social_signals(product_name):
    """
    Collect social signals for a smart baby tech product.
    Returns dict with engagement metrics and content opportunities.
    """
    signals = {
        "product": product_name,
        "timestamp": datetime.now().isoformat(),
        "tiktok_mentions": 0,
        "instagram_mentions": 0,
        "forum_mentions": 0,
        "jiji_mentions": 0,
        "facebook_mentions": 0,
        "content_opportunities": [],
        "demand_score": 0.0,
        "recommendation": "WATCH"
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }
    
    # BabyCenter search
    try:
        url = f"https://www.babycenter.com/search?q={quote_plus(product_name)}"
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            signals["forum_mentions"] = resp.text.count(product_name.split()[0].lower())
    except Exception as e:
        logger.warning("babycenter_signal_failed", product=product_name, error=str(e))
    
    # Mumsnet search
    try:
        url = f"https://www.mumsnet.com/Talk?q={quote_plus(product_name)}"
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            signals["forum_mentions"] += resp.text.count(product_name.split()[0].lower()) // 2
    except Exception as e:
        logger.warning("mumsnet_signal_failed", product=product_name, error=str(e))
    
    # Jiji search (Kenyan marketplace)
    try:
        url = f"https://jiji.co.ke/search?query={quote_plus(product_name)}"
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            signals["jiji_mentions"] = resp.text.count('item-card') // 3
    except Exception as e:
        logger.warning("jiji_signal_failed", product=product_name, error=str(e))
    
    # Facebook Marketplace search
    try:
        url = f"https://www.facebook.com/marketplace/search/?query={quote_plus(product_name)}"
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            signals["facebook_mentions"] = resp.text.count('marketplace') // 5
    except Exception as e:
        logger.warning("facebook_signal_failed", product=product_name, error=str(e))
    
    # Calculate demand score
    total_mentions = (
        signals["tiktok_mentions"] * 3 +  # TikTok weighted higher (viral potential)
        signals["instagram_mentions"] * 2 +
        signals["forum_mentions"] * 1 +
        signals["jiji_mentions"] * 4 +  # Jiji weighted highest (actual market)
        signals["facebook_mentions"] * 2
    )
    signals["demand_score"] = min(total_mentions / 100, 1.0)
    
    if signals["demand_score"] > 0.5:
        signals["recommendation"] = "CREATE CONTENT"
    elif signals["demand_score"] > 0.2:
        signals["recommendation"] = "WATCH"
    else:
        signals["recommendation"] = "WAIT"
    
    # Generate content opportunities
    product_data = SMART_BABY_TECH_PRODUCTS.get(product_name, {})
    for angle in product_data.get("content_angles", [])[:2]:
        signals["content_opportunities"].append({
            "type": "content",
            "angle": angle,
            "platform": "tiktok",
            "priority": "HIGH" if signals["demand_score"] > 0.3 else "MEDIUM"
        })
    
    return signals

def generate_content_calendar(product_name, num_posts=7):
    """
    Generate a content calendar for a product.
    Returns list of content ideas.
    """
    product_data = SMART_BABY_TECH_PRODUCTS.get(product_name, {})
    content_ideas = []
    
    platforms = ["TikTok", "Instagram Reels", "YouTube Shorts", "Facebook"]
    content_types = [
        "Educational - pain point solve",
        "Unboxing/Review",
        "Comparison",
        "How-to/Setup",
        "Parent testimonial",
        "Quick tips"
    ]
    
    for i in range(num_posts):
        platform = platforms[i % len(platforms)]
        content_type = content_types[i % len(content_types)]
        angle = product_data.get("content_angles", ["General"])[i % len(product_data.get("content_angles", ["General"]))]
        
        content_ideas.append({
            "day": i + 1,
            "product": product_name,
            "platform": platform,
            "type": content_type,
            "angle": angle,
            "caption_template": f"🇰🇪 New Kenyan parents! Have you heard about {product_name}? {angle} 🤔\n.\n.\n.\n#newmomkenya #parentingtips #smartparenting",
            "hashtags": "#smartbabytech #newmomkenya #parentingtips #babytech #kenyanparents"
        })
    
    return content_ideas

def main():
    print(f"🕒 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} Smart Baby Tech Demand Generation")
    print()
    
    # Ensure output directory exists
    output_dir = "data/demand_gen/smart_baby_tech"
    ensure_dir(output_dir)
    
    # 1. Collect demand signals for each product
    print("📊 Collecting demand signals for smart baby tech products...")
    all_signals = []
    
    for product in SMART_BABY_TECH_PRODUCTS.keys():
        signals = collect_social_signals(product)
        all_signals.append(signals)
        print(f"  {product}: demand_score={signals['demand_score']:.3f}, recommendation={signals['recommendation']}")
    
    # 2. Identify top opportunity
    top_product = max(all_signals, key=lambda x: x["demand_score"])
    print(f"\n🏆 Top opportunity: {top_product['product']} (score: {top_product['demand_score']:.3f})")
    print(f"   Recommendation: {top_product['recommendation']}")
    
    # 3. Generate content calendar for top product
    print(f"\n📅 Generating content calendar for {top_product['product']}...")
    content_calendar = generate_content_calendar(top_product['product'], num_posts=7)
    
    # Save content calendar
    calendar_path = f"{output_dir}/content_calendar.csv"
    with open(calendar_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=["day", "product", "platform", "type", "angle", "caption_template", "hashtags"])
        writer.writeheader()
        writer.writerows(content_calendar)
    print(f"  📝 Content calendar saved: {calendar_path}")
    
    # 4. Generate campaign performance report
    print(f"\n📈 Generating campaign performance report...")
    report = {
        "timestamp": datetime.now().isoformat(),
        "products_analyzed": len(SMART_BABY_TECH_PRODUCTS),
        "top_opportunity": top_product['product'],
        "demand_signals": all_signals,
        "next_actions": [
            f"Create TikTok content for {top_product['product']}",
            "Identify 3 micro-influencers in Kenyan parenting space",
            "Set up affiliate tracking for Jiji listings",
            "Monitor competitor activity on Facebook Marketplace"
        ]
    }
    
    report_path = f"{output_dir}/campaign_report.json"
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    print(f"  📝 Campaign report saved: {report_path}")
    
    # 5. Output summary
    print(f"\n{'='*60}")
    print(f"📊 SMART BABY TECH DEMAND GENERATION SUMMARY")
    print(f"{'='*60}")
    print(f"\n🏆 TOP OPPORTUNITY: {top_product['product']}")
    print(f"   Demand Score: {top_product['demand_score']:.3f}")
    print(f"   Recommendation: {top_product['recommendation']}")
    print(f"\n📋 NEXT ACTIONS:")
    for i, action in enumerate(report['next_actions'], 1):
        print(f"   {i}. {action}")
    print(f"\n📁 OUTPUT FILES:")
    print(f"   - Content Calendar: {calendar_path}")
    print(f"   - Campaign Report: {report_path}")
    print(f"\n💡 DEMAND GENERATION INSIGHTS:")
    for product, data in SMART_BABY_TECH_PRODUCTS.items():
        print(f"   • {product} ({data['price_range_usd']}): {data['description']}")
    print(f"\n{'='*60}")
    
    # 6. Save campaign tracker
    tracker_path = f"{output_dir}/campaign_tracker.csv"
    rows = []
    if os.path.exists(tracker_path):
        with open(tracker_path, 'r') as f:
            reader = csv.reader(f)
            rows = list(reader)
    
    # Add new row
    row = [
        datetime.now().isoformat(),
        top_product['product'],
        f"{top_product['demand_score']:.3f}",
        top_product['recommendation'],
        len(content_calendar),
        "pending"
    ]
    rows.append(row)
    
    with open(tracker_path, 'w', newline='') as f:
        writer = csv.writer(f)
        if not rows or rows[0][0] != 'timestamp':
            writer.writerow(['timestamp', 'top_product', 'demand_score', 'recommendation', 'content_pieces', 'status'])
        writer.writerows(rows)
    
    print(f"\n✅ Demand generation task complete!")
    print(f"   Campaign tracker updated: {tracker_path}")

if __name__ == "__main__":
    main()