#!/usr/bin/env python3
"""
Generate weekly demand generation ideas for baby-arb-ke project.
Reads latest demand scout data, formats detailed ideas for low-signal categories.
"""

import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import quote_plus

def load_demand_scout():
    """Load the latest demand scout JSON."""
    script_dir = Path(__file__).resolve().parent.parent  # skill dir
    demand_path = Path("data/cache/demand_scout/latest.json")
    if not demand_path.is_absolute():
        demand_path = Path.cwd() / demand_path
    if not demand_path.exists():
        print(f"ERROR: Demand scout file not found at {demand_path}", file=sys.stderr)
        sys.exit(1)
    mtime = datetime.fromtimestamp(demand_path.stat().st_mtime, tz=timezone.utc)
    age = datetime.now(timezone.utc) - mtime
    if age.days >= 2:
        print(f"WARNING: Demand scout data is {age.days} days old.", file=sys.stderr)
    try:
        with open(demand_path, 'r') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"ERROR: Failed to parse JSON: {e}", file=sys.stderr)
        sys.exit(1)
    return data

def load_target_categories():
    """Load target categories from config file if exists, else default."""
    config_path = Path("config/target_categories.yaml")
    if not config_path.is_absolute():
        config_path = Path.cwd() / config_path
    default = ["car seat", "stroller", "nursery", "feeding"]
    if config_path.exists():
        try:
            import yaml
            with open(config_path, 'r') as f:
                cats = yaml.safe_load(f)
                if isinstance(cats, list) and all(isinstance(c, str) for c in cats):
                    return cats
        except Exception:
            pass
    return default

def get_category_score(products, category):
    """Find the highest demand score for a given category in products list."""
    best_score = 0.0
    best_confidence = ""
    for p in products:
        if p.get("category", "").lower() == category.lower():
            score = p.get("demand_score", 0.0)
            if score > best_score:
                best_score = score
                best_confidence = p.get("confidence", "")
    return best_score, best_confidence

def build_marketplace_urls(product_name):
    """Build search URLs for major marketplaces."""
    query = quote_plus(product_name)
    return {
        "eBay": f"https://www.ebay.com/sch/i.html?_nkw={query}",
        "Mercari": f"https://www.mercari.com/search/?keyword={query}",
        "Facebook Marketplace": f"https://www.facebook.com/marketplace/search/?query={query}",
        "OfferUp": f"https://offerup.com/search/?q={query}",
    }

def format_price_usd(cost_usd):
    """Format USD price with two decimals."""
    return f"${cost_usd:.2f}"

def generate_ideas_for_category(category, score, confidence):
    """Generate detailed ideas block for a category."""
    # Normalize category for matching
    cat_lower = category.lower()
    # Status line
    if score < 0.2:
        status = f"No recent listings in demand scout (score < 0.2)"
    elif score < 0.4:
        status = f"Low signal – score {score:.2f} ({confidence})"
    else:
        status = f"Moderate signal – score {score:.2f} ({confidence})"
    # Why section
    why_map = {
        "nursery": "High margin potential, universal need, gifting opportunity, low local production.",
        "feeding": "Essential product, repeat purchase potential, compatible with local habits, high turnover.",
        "car seat": "Safety-critical, high ticket size, regulatory compliance builds trust, seasonal peaks.",
        "stroller": "High visibility, social sharing potential, strong resale value, travel system appeal."
    }
    why = why_map.get(cat_lower, "Opportunity to fill market gap and build brand authority.")
    # Content themes
    themes_map = {
        "nursery": [
            "TikTok: #KenyanNurseryDecor challenge – show room transformation with a blanket or swaddle.",
            "Instagram Reels: “Before/after” nursery setup using KE‑priced items (under KES 5,000).",
            "YouTube Shorts: “5 nursery essentials under KES 10,000” – feature the product.",
            "Pinterest-inspired boards: Create and share mood boards for different nursery themes."
        ],
        "feeding": [
            "TikTok: Side-by-side warming tests – US bottle vs local bottle (speed, safety).",
            "Instagram Reels: “A day in the life” – feeding routine with the product.",
            "Facebook Live: Q&A with a pediatrician on bottle safety and preparation.",
            "User-generated content: Encourage moms to share their feeding hacks using the product."
        ],
        "car seat": [
            "TikTok: Correct installation demonstration (rear‑forward, latch vs seatbelt).",
            "Instagram Reels: “Travel system stroller + car seat” combo walkthrough.",
            "Facebook: Host a virtual car seat safety check event with a certified technician.",
            "YouTube: “Myths vs facts” about car seat expiry and second‑hand safety."
        ],
        "stroller": [
            "TikTok: “Stroller Safari” – test the stroller on different terrains (pavement, grass, dirt).",
            "Instagram Reels: “One‑hand fold” challenge – show how quick and easy it is.",
            "Facebook: Collaborate with mommy bloggers for a “stroller review” series.",
            "TikTok: Stroller accessories hack – diaper bag attachment, cup holder, etc."
        ]
    }
    themes = themes_map.get(cat_lower, [
        "Create educational content about the product’s benefits.",
        "Show real-life usage scenarios with local families.",
        "Highlight cost savings compared to buying new locally."
    ])
    # Influencer outreach
    influencer_map = {
        "nursery": "Partner with 3‑5 mommy influencers (5k‑50k followers) for nursery setup unboxing and room tour.",
        "feeding": "Engage 2‑3 parenting influencers or pediatricians for feeding safety talks and product demos.",
        "car seat": "Collaborate with certified car seat technicians (often found via hospitals or NGOs) for safety events.",
        "stroller": "Work with lifestyle influencers who focus on travel, outdoor activities, or toddler adventures."
    }
    influencer = influencer_map.get(cat_lower, "Identify 2‑4 local influencers aligned with the product’s use case for authentic reviews.")
    # Local partnerships
    partnerships_map = {
        "nursery": "Approach maternity hospitals for product seeding in welcome packs; collaborate with baby boutiques for co‑hosted virtual nursery workshops.",
        "feeding": "Partner with local lactation consultants, baby-weaning workshops, and maternal health clinics.",
        "car seat": "Team up with National Transport and Safety Authority (NTSA) or local police for road safety campaigns.",
        "stroller": "Partner with malls, supermarkets, and recreational parks for stroller‑friendly routes and parking."
    }
    partnerships = partnerships_map.get(cat_lower, "Reach out to relevant local businesses, clinics, or community groups for product placement or co‑marketing.")
    # Promotional tactics
    promo_map = {
        "nursery": "Launch bundle: blanket + sheet set at 10% off; run a “Refer a friend” giveaway – both get 15% off next purchase.",
        "feeding": "Offer a “first‑time buyer” discount code; create a feeding starter pack (bottle + warmer + brush) at a special price.",
        "car seat": "Provide free installation service with every purchase; run a “trade‑in old car seat” discount (if not expired).",
        "stroller": "Bundle with a diaper bag or rain cover at a special price; offer free delivery within Nairobi for orders over KES 15,000."
    }
    promo = promo_map.get(cat_lower, "Run limited‑time discount codes; create bundle deals with complementary items; consider a loyalty program for repeat buyers.")
    # Hashtags & copy
    hashtags_map = {
        "nursery": "#KenyanNursery, #BabyBlanketKE, #CozyKeiki, #NurseryInspoKE",
        "feeding": "#BabyFeedingKE, #BottleWarmerKE, #MomLifeKE, #FeedingMadeEasy",
        "car seat": "#CarSeatSafetyKE, #SafeTravelKE, #BabyOnBoardKE, #CarSeatCheck",
        "stroller": "#StrollerKe, #BabyOnTheGoKE, #StrollerLifeKE, #MommyMovesKE"
    }
    hashtags = hashtags_map.get(cat_lower, "#BabyArbKE, #KenyanParents, #BabyGearKE, #SmartParentingKE")
    sample_caption = f"Discover the {category} that’s saving Kenyan parents hundreds. Swipe to see why it’s a game‑changer! 👇"
    # Effort and timeline
    effort_map = {
        "nursery": "Medium",
        "feeding": "Medium",
        "car seat": "High (due to compliance checks)",
        "stroller": "Medium"
    }
    effort = effort_map.get(cat_lower, "Medium")
    timeline = "Start teaser mid‑week, influencer push weekend, paid ads early next week."
    
    ideas = []
    ideas.append(f"   Status: {status}")
    ideas.append(f"   Why: {why}")
    ideas.append("   Content Themes:")
    for t in themes:
        ideas.append(f"     - {t}")
    ideas.append("   Influencer Outreach:")
    ideas.append(f"     - {influencer}")
    ideas.append("   Local Partnerships:")
    ideas.append(f"     - {partnerships}")
    ideas.append("   Promotional Tactics:")
    ideas.append(f"     - {promo}")
    ideas.append(f"   Hashtags & Copy:")
    ideas.append(f"     - {hashtags}")
    ideas.append(f"     - Sample caption: “{sample_caption}”")
    ideas.append(f"   Effort: {effort} | Timeline: {timeline}")
    return "\n".join(ideas)

def main():
    data = load_demand_scout()
    target_cats = load_target_categories()
    products = data.get("products", [])
    generated_at = data.get("generated_at", "")
    # Determine week range (Monday to Sunday) based on generated_at or today
    try:
        dt = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
    except Exception:
        dt = datetime.now(timezone.utc)
    # Start of week (Monday)
    start_of_week = dt - timedelta(days=dt.weekday())
    end_of_week = start_of_week + timedelta(days=6)
    date_str = f"{start_of_week.strftime('%Y-%m-%d')} to {end_of_week.strftime('%Y-%m-%d')}"
    
    lines = []
    lines.append(f"🗓️ Week of {date_str} Weekly Baby‑Arb‑Ke Demand Generation")
    lines.append("")
    lines.append("🟡 WEEKLY DEMAND GENERATION FOCUS")
    
    any_low = False
    for cat in target_cats:
        score, confidence = get_category_score(products, cat)
        # Consider low signal if score < 0.4 or category not found (score 0.0)
        if score < 0.4:
            any_low = True
            lines.append("")
            lines.append(f"• {cat.title()}")
            ideas_block = generate_ideas_for_category(cat, score, confidence)
            # Indent the ideas block
            for line in ideas_block.split("\n"):
                lines.append(f"   {line}")
    
    if not any_low:
        lines.append("")
        lines.append("All target categories currently have moderate or high signal (score >= 0.4).")
        lines.append("Consider reviewing margin reports or exploring adjacent categories for opportunities.")
    
    lines.append("")
    lines.append("---")
    lines.append("*Generated by Hermes Agent – weekly-demand-generation skill*")
    
    message = "\n".join(lines)
    if len(message) > 3500:
        message = message[:3500] + "\n\n... (truncated)"
    print(message)

if __name__ == "__main__":
    main()