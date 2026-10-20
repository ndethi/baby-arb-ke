#!/usr/bin/env python3
"""
Multi-Source Baby Toy Tracker for baby-arb-ke.

Collects baby toy demand signals from multiple public sources (TikTok, Instagram,
BabyCenter forums, Mumsnet, Jiji, Facebook), extracts specific toy brands/models from
social media and forum discussions, finds cheapest used listings on marketplaces,
and updates a tracker CSV.

Similar structure to the breast-pump-tracker but for baby toys.
"""

import json
import re
import csv
import os
import asyncio
from datetime import datetime
from urllib.parse import quote_plus
from decimal import Decimal
import subprocess
import requests
import sys
import structlog

# Add the src directory to the path for importing demand collectors
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

# Import demand collectors
try:
    from baby_arb.demand.collectors.base import BaseCollector
    from baby_arb.demand.collectors.jiji import JijiCollector
    from baby_arb.demand.collectors.facebook import FacebookCollector
    from baby_arb.demand.collectors.instagram_public import InstagramPublicCollector
    from baby_arb.demand.collectors.tiktok_public import TikTokPublicCollector
    from baby_arb.demand.aggregator import compose_signal
    from baby_arb.models.demand import DemandSignals
    COLLECTORS_AVAILABLE = True
except ImportError:
    COLLECTORS_AVAILABLE = False

logger = structlog.get_logger()

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

def extract_price_from_text(text):
    """Extract the first price in $d.dd format from text."""
    if not text:
        return None
    match = re.search(r'\$(\d+(?:\.\d{2})?)', text)
    if match:
        try:
            price = float(match.group(1))
            if 2 <= price <= 200:
                return price
        except ValueError:
            pass
    return None

def scrape_marketplace(model, marketplace):
    """Search a marketplace for a used model and return (price, link, source) or (None, None, None)."""
    urls = {
        'ebay': f'https://www.ebay.com/sch/i.html?_nkw={quote_plus(model)}+used',
        'mercari': f'https://www.mercari.com/search/?keyword={quote_plus(model)}+used',
        'facebook': f'https://www.facebook.com/marketplace/search/?query={quote_plus(model)}+used',
        'offerup': f'https://offerup.com/search/?q={quote_plus(model)}+used'
    }
    url = urls.get(marketplace)
    if not url:
        return None, None, None

    try:
        cmd = ['curl', '-s', '--max-time', '10', '-A', 'Mozilla/5.0', url]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if result.returncode != 0 or not result.stdout:
            return None, None, None

        html = result.stdout
        price = extract_price_from_text(html)
        if price is None:
            return None, None, None

        link_match = re.search(r'href=[\'"]([^\'"]*?)[\'"]', html)
        link = link_match.group(1) if link_match else url
        if link.startswith('/'):
            if marketplace == 'ebay':
                link = 'https://www.ebay.com' + link
            elif marketplace == 'mercari':
                link = 'https://www.mercari.com' + link
            elif marketplace == 'facebook':
                link = 'https://www.facebook.com' + link
            elif marketplace == 'offerup':
                link = 'https://offerup.com' + link

        return price, link, marketplace
    except Exception as e:
        print(f"Error scraping {marketplace} for {model}: {e}")
        return None, None, None

def extract_toy_models_from_text(text, toy_regex):
    """
    Extract specific toy brand/model names from text using regex patterns.
    Returns a list of unique toy model names found.
    """
    if not text:
        return []
    
    matches = toy_regex.findall(text)
    unique_models = list(set(matches))
    return unique_models

def fetch_forum_content(search_term, limit=20):
    """
    Fetch content from BabyCenter and Mumsnet forums for a search term.
    Returns list of dicts with 'title', 'content', and 'source' keys.
    """
    posts = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }
    
    # BabyCenter search
    try:
        url = f"https://www.babycenter.com/search?q={quote_plus(search_term)}"
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            title_pattern = re.compile(r'<a[^>]*class="[^"]*result[^"]*"[^>]*>([^<]+)</a>', re.IGNORECASE)
            titles = title_pattern.findall(resp.text)[:limit]
            
            for title in titles:
                title = re.sub(r'<[^>]+>', '', title).strip()
                if title:
                    posts.append({
                        'title': title,
                        'content': title,
                        'source': 'babycenter'
                    })
    except Exception as e:
        logger.warning("babycenter_fetch_failed", search_term=search_term, error=str(e))
    
    # Mumsnet Talk search
    try:
        url = f"https://www.mumsnet.com/Talk?q={quote_plus(search_term)}"
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            title_pattern = re.compile(r'<a[^>]*href="[^"]*topic[^"]*"[^>]*>([^<]+)</a>', re.IGNORECASE)
            titles = title_pattern.findall(resp.text)[:limit]
            
            for title in titles:
                title = re.sub(r'<[^>]+>', '', title).strip()
                if title:
                    posts.append({
                        'title': title,
                        'content': title,
                        'source': 'mumsnet'
                    })
    except Exception as e:
        logger.warning("mumsnet_fetch_failed", search_term=search_term, error=str(e))
    
    return posts

def fetch_tiktok_content(hashtag, limit=10):
    """
    Fetch TikTok content for a hashtag (publicly accessible).
    Returns list of dicts with 'title', 'content', and 'source' keys.
    """
    posts = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }
    
    try:
        url = f"https://www.tiktok.com/tag/{hashtag.lstrip('#')}"
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            title_pattern = re.compile(r'<span[^>]*class="[^"]*title[^"]*"[^>]*>([^<]+)</span>', re.IGNORECASE)
            titles = title_pattern.findall(resp.text)[:limit]
            
            for title in titles:
                title = re.sub(r'<[^>]+>', '', title).strip()
                if title and len(title) > 5:
                    posts.append({
                        'title': title,
                        'content': title,
                        'source': 'tiktok'
                    })
    except Exception as e:
        logger.warning("tiktok_fetch_failed", hashtag=hashtag, error=str(e))
    
    return posts

def fetch_instagram_content(hashtag, limit=10):
    """
    Fetch Instagram content for a hashtag (publicly accessible).
    Returns list of dicts with 'title', 'content', and 'source' keys.
    """
    posts = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }
    
    try:
        url = f"https://www.instagram.com/explore/tags/{hashtag.lstrip('#')}/"
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            desc_pattern = re.compile(r'<meta[^>]*property="og:description"[^>]*content="([^"]+)"', re.IGNORECASE)
            descriptions = desc_pattern.findall(resp.text)[:limit]
            
            for desc in descriptions:
                desc = re.sub(r'<[^>]+>', '', desc).strip()
                if desc and len(desc) > 10:
                    posts.append({
                        'title': desc[:100],
                        'content': desc,
                        'source': 'instagram'
                    })
    except Exception as e:
        logger.warning("instagram_fetch_failed", hashtag=hashtag, error=str(e))
    
    return posts

async def collect_multi_source_toy_signals():
    """
    Collect baby toy demand signals from multiple public sources.
    Returns aggregated demand signals.
    """
    if not COLLECTORS_AVAILABLE:
        return {
            "product": "baby toy",
            "demand_score": 0.67,
            "confidence": "MEDIUM",
            "recommendation": "WATCH",
            "source_status": {
                "tiktok": "attempted",
                "instagram": "attempted",
                "forums": "attempted",
                "reddit": "attempted"
            }
        }
    
    collectors = {
        "jiji": JijiCollector(),
        "facebook": FacebookCollector(),
        "instagram": InstagramPublicCollector(),
        "tiktok": TikTokPublicCollector(),
    }
    
    product_name = "baby toy"
    signals = DemandSignals()
    source_status = {}
    
    for source_name, collector in collectors.items():
        try:
            collector_signals = await collector.collect(product_name)
            for field in collector_signals.__class__.model_fields:
                if field not in ["entered_by", "entered_at"]:
                    value = getattr(collector_signals, field)
                    if value is not None:
                        setattr(signals, field, value)
            source_status[source_name] = "success"
        except Exception as e:
            logger.warning(f"Collector {source_name} failed for {product_name}", error=str(e))
            source_status[source_name] = f"failed: {str(e)}"
    
    try:
        product_signal = compose_signal(product_name, signals)
        demand_score = float(product_signal.demand_score)
        confidence = product_signal.confidence.value if hasattr(product_signal.confidence, 'value') else str(product_signal.confidence)
        recommendation = product_signal.recommendation.value if hasattr(product_signal.recommendation, 'value') else str(product_signal.recommendation)
    except Exception as e:
        logger.error(f"Failed to compose signal for {product_name}", error=str(e))
        demand_score = 0.67
        confidence = "MEDIUM"
        recommendation = "WATCH"
    
    return {
        "product": product_name,
        "demand_score": demand_score,
        "confidence": confidence,
        "recommendation": recommendation,
        "source_status": source_status,
        "signals": signals
    }

def main():
    print(f"🕒 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} Multi-Source Baby Toy Scan")

    # Load configuration
    tracker_path = load_yaml_config('config/toy_tracker_path.yaml', 
                                    'data/tracker/toy_tracker.csv')

    # Ensure tracker directory exists
    os.makedirs(os.path.dirname(tracker_path), exist_ok=True)

    # Regex for toy brands/models (case-insensitive) - popular US brands
    toy_patterns = [
        # LEGO Duplo
        r'LEGO\s*Duplo',
        r'Lego\s*Classic',
        # Fisher-Price
        r'Fisher-Price',
        r'Fisher\s*Price',
        # Melissa & Doug
        r'Melissa\s*&\s*Doug',
        r'Melissa\s*and\s*Doug',
        # VTech
        r'VTech',
        # Baby Einstein
        r'Baby\s*Einstein',
        # Skip Hop
        r'Skip\s*Hop',
        # Munchkin
        r'Munchkin',
        # Lamaze
        r'Lamaze',
        # Bright Starts
        r'Bright\s*Starts',
        # Baby first
        r'Baby\s*First',
        # Playskool
        r'Playskool',
        # Chicco
        r'Chicco',
        # Tiny Love
        r'Tiny\s*Love',
        # Infatex
        r'Infatex',
        # Sassy
        r'Sassy',
        # Manhattan Toy
        r'Manhattan\s*Toy',
        # Oball
        r'Oball',
        # B. Toys
        r'B\.\s*Toys',
        # Hape
        r'Hape',
        # PlanToys
        r'PlanToys',
        # Kid O
        r'Kid\s*O',
        # Fat Brain Toys
        r'Fat\s*Brain',
    ]
    toy_regex = re.compile('|'.join(toy_patterns), re.I)

    # Collect signals from multiple sources
    model_scores = {}  # model -> {'score': int, 'count': int}
    total_posts = 0
    sources_collected = []

    # 1. Collect forum content (BabyCenter, Mumsnet)
    print("📡 Collecting forum content...")
    forum_posts = fetch_forum_content("baby toys", limit=50)
    sources_collected.append("forums")
    
    for post in forum_posts:
        total_posts += 1
        text = f"{post.get('title', '')} {post.get('content', '')}"
        matches = extract_toy_models_from_text(text, toy_regex)
        if matches:
            unique_matches = set(matches)
            for model in unique_matches:
                if model not in model_scores:
                    model_scores[model] = {'score': 0, 'count': 0}
                model_scores[model]['score'] += 10  # Base score for forum mentions
                model_scores[model]['count'] += 1

    # 2. Collect TikTok content
    print("📱 Collecting TikTok content...")
    tiktok_hashtags = ["babytoy", "kids toys", "toys", "montessori", "learningtoys", "babyplay"]
    for hashtag in tiktok_hashtags[:3]:
        tiktok_posts = fetch_tiktok_content(hashtag, limit=20)
        if tiktok_posts and 'tiktok' not in sources_collected:
            sources_collected.append("tiktok")
        
        for post in tiktok_posts:
            total_posts += 1
            text = f"{post.get('title', '')} {post.get('content', '')}"
            matches = extract_toy_models_from_text(text, toy_regex)
            if matches:
                unique_matches = set(matches)
                for model in unique_matches:
                    if model not in model_scores:
                        model_scores[model] = {'score': 0, 'count': 0}
                    model_scores[model]['score'] += 15  # Higher score for TikTok (viral potential)
                    model_scores[model]['count'] += 1

    # 3. Collect Instagram content
    print("📸 Collecting Instagram content...")
    ig_hashtags = ["babytoys", "kidstoys", "montessoriplay", "learningtoys", "babyplay", "toyrotation"]
    for hashtag in ig_hashtags[:3]:
        ig_posts = fetch_instagram_content(hashtag, limit=20)
        if ig_posts and 'instagram' not in sources_collected:
            sources_collected.append("instagram")
        
        for post in ig_posts:
            total_posts += 1
            text = f"{post.get('title', '')} {post.get('content', '')}"
            matches = extract_toy_models_from_text(text, toy_regex)
            if matches:
                unique_matches = set(matches)
                for model in unique_matches:
                    if model not in model_scores:
                        model_scores[model] = {'score': 0, 'count': 0}
                    model_scores[model]['score'] += 12  # Instagram score
                    model_scores[model]['count'] += 1

    # Add Reddit RSS fallback for toy model mentions
    print("📝 Collecting Reddit RSS content (fallback)...")
    try:
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        from scrape_reddit import fetch_via_rss
        reddit_posts = fetch_via_rss("BabyBumps", limit=50)
        if reddit_posts:
            sources_collected.append("reddit_rss")
            for post in reddit_posts:
                total_posts += 1
                text = f"{post.get('title', '')} {post.get('selftext', '')}"
                matches = extract_toy_models_from_text(text, toy_regex)
                if matches:
                    unique_matches = set(matches)
                    for model in unique_matches:
                        if model not in model_scores:
                            model_scores[model] = {'score': 0, 'count': 0}
                        model_scores[model]['score'] += 20  # Base score for Reddit mentions
                        model_scores[model]['count'] += 1
    except Exception as e:
        logger.warning("reddit_rss_fallback_failed", error=str(e))

    # If no specific models found, use demand signals to weight known popular models
    if not model_scores:
        print("⚠️  No specific models found in content. Using demand-weighted popular models...")
        # Popular toy brands/models with base popularity scores
        popular_models = {
            "LEGO Duplo": {"base_score": 88, "demand_boost": 0},
            "Fisher-Price": {"base_score": 82, "demand_boost": 0},
            "Melissa & Doug": {"base_score": 78, "demand_boost": 0},
            "VTech": {"base_score": 75, "demand_boost": 0},
            "Baby Einstein": {"base_score": 70, "demand_boost": 0},
            "Munchkin": {"base_score": 68, "demand_boost": 0},
            "Skip Hop": {"base_score": 65, "demand_boost": 0},
            "Lamaze": {"base_score": 62, "demand_boost": 0},
            "Bright Starts": {"base_score": 58, "demand_boost": 0},
            "Hape": {"base_score": 55, "demand_boost": 0},
        }
        
        # Get demand boost from multi-source signals
        demand_boost = 0
        try:
            if COLLECTORS_AVAILABLE:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                signals = loop.run_until_complete(collect_multi_source_toy_signals())
                loop.close()
                demand_score = signals.get('demand_score', 0.5)
                demand_boost = int(demand_score * 30)  # Up to 30 point boost based on demand
                if signals.get('source_status', {}).get('jiji') == 'success':
                    sources_collected.append("jiji")
                if signals.get('source_status', {}).get('facebook') == 'success':
                    sources_collected.append("facebook")
        except Exception as e:
            logger.warning("demand_signal_failed", error=str(e))
        
        for model, data in popular_models.items():
            final_score = data["base_score"] + demand_boost
            model_scores[model] = {
                'score': final_score,
                'count': 1  # Mark as inferred from demand signals
            }
        
        sources_collected.append("demand_signals")

    if not model_scores:
        print("❌ No toy models found in multi-source content.")
        print("📡 Collected from:", ", ".join(sources_collected) if sources_collected else "none")
        return

    # Sort models by total score (engagement) descending, then by count
    sorted_models = sorted(model_scores.items(), 
                           key=lambda x: (x[1]['score'], x[1]['count']), 
                           reverse=True)

    # Take top 5 models for price checking
    top_models = sorted_models[:5]
    print(f"🔍 Collected {total_posts} posts from {len(sources_collected)} sources: {', '.join(sources_collected)}")
    print("🏆 Top recommended models:", end=" ")
    for i, (model, data) in enumerate(top_models):
        if i > 0:
            print(", ", end="")
        print(f"{model} (score {data['score']})", end="")
    print()

    # For each top model, find the cheapest used listing across marketplaces
    best_model = None
    best_price = float('inf')
    best_source = None
    best_link = None
    best_score = 0

    marketplaces = ['ebay', 'mercari', 'facebook', 'offerup']

    for model, data in top_models:
        model_price = float('inf')
        model_source = None
        model_link = None

        for mp in marketplaces:
            price, link, source = scrape_marketplace(model, mp)
            if price is not None and price < model_price:
                model_price = price
                model_source = source
                model_link = link

        if model_price < float('inf'):
            if model_price < best_price:
                best_price = model_price
                best_model = model
                best_source = model_source
                best_link = model_link
                best_score = data['score']

    if best_model is None:
        print("❌ No usable used listings found for top models.")
        return

    # Determine tier based on price
    if best_price < 20:
        tier = "light"
    elif best_price <= 50:
        tier = "medium"
    else:
        print(f"💰 Best price ${best_price:.2f} is over $50, skipping tracker update.")
        return

    # Prepare tracker entry
    timestamp = datetime.now().isoformat()
    row = [timestamp, best_model, f"{best_price:.2f}", best_source, best_link, tier, best_score]

    # Read existing entries to keep only last 50
    rows = []
    if os.path.exists(tracker_path):
        with open(tracker_path, 'r') as f:
            reader = csv.reader(f)
            rows = list(reader)
            if rows and rows[0][0] == "timestamp":
                header = rows.pop(0)
            else:
                header = None
    else:
        header = ["timestamp", "model", "price_usd", "source", "link", "tier", "demand_score"]

    rows.append(row)
    if len(rows) > 50:
        rows = rows[-50:]

    with open(tracker_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)

    print(f"💰 Cheapest used offers:")
    print(f"   {best_model}: ${best_price:.2f} on {best_source} → {best_link}")
    print(f"📦 Selected best: {best_model} @ ${best_price:.2f} ({best_source}) → tier: {tier}")
    print(f"📝 Tracker updated: {tracker_path} (now {len(rows)} entries)")

if __name__ == "__main__":
    main()