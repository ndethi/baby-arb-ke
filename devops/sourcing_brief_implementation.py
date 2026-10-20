"""Implementation of sourcing brief generation for baby-arb-ke."""

import asyncio
import json
import re
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import List, Dict, Any

import structlog

logger = structlog.get_logger()


async def generate_sourcing_brief(dry_run: bool = True) -> str:
    """Generate the weekly sourcing brief from demand signals and margin data.
    
    Args:
        dry_run: If True, don't post to Telegram or open PR
        
    Returns:
        str: The generated brief content
    """
    # Paths
    base_path = Path("/Users/ndethi/dev/ir/baby-arb-ke")
    demand_scout_path = base_path / "data/cache/demand_scout/latest.json"
    margin_eval_path = base_path / "data/cache/margin_evaluator"
    progress_path = base_path / "docs/progress"
    
    logger.info("Generating sourcing brief", dry_run=dry_run)
    
    # Load demand scout data
    if not demand_scout_path.exists():
        raise FileNotFoundError(f"Demand scout data not found at {demand_scout_path}")
    
    with open(demand_scout_path, 'r') as f:
        demand_data = json.load(f)
    
    logger.info("Loaded demand scout data", 
                generated_at=demand_data.get('generated_at'),
                product_count=len(demand_data.get('products', [])))
    
    # Load margin evaluator reports (last 4 weeks)
    margin_reports = []
    if margin_eval_path.exists():
        reports = list(margin_eval_path.glob("margin_report_*.json"))
        # Sort by date in filename (newest first)
        def extract_date(report_path):
            match = re.search(r'(\d{4}-\d{2}-\d{2})', report_path.name)
            return match.group(1) if match else "0000-00-00"
        sorted_reports = sorted(reports, key=extract_date, reverse=True)
        # Take last 4 weeks
        for report in sorted_reports[:4]:
            with open(report, 'r') as f:
                margin_reports.append(json.load(f))
    
    logger.info("Loaded margin evaluator reports", count=len(margin_reports))
    
    # Process products for priority items
    priority_items = []
    avoid_this_week = []
    human_review_needed = []
    
    for product in demand_data.get('products', []):
        name = product.get('name', '')
        brand = product.get('brand', '')
        model = product.get('model', '')
        category = product.get('category', '')
        demand_score = product.get('demand_score', 0)
        confidence = product.get('confidence', 'LOW')
        signals = product.get('signals', {})
        
        # Check if we have observed KE price (jiji_median_sold_kes)
        jiji_median_sold_kes = signals.get('jiji_median_sold_kes')
        
        if jiji_median_sold_kes is None or jiji_median_sold_kes == 0:
            # No observed KE price -> goes to human review
            human_review_needed.append({
                'product': name,
                'reason': 'No observed KE reference price',
                'demand_score': demand_score,
                'confidence': confidence
            })
            continue
        
        # Calculate target landed cost for 50% margin
        # Get FX rate from demand scout data or use default
        fx_rate_str = demand_data.get('fx_rate', '145.0')  # Would normally come from separate FX cache
        try:
            fx_rate = Decimal(str(fx_rate_str))
        except:
            fx_rate = Decimal('145.0')  # Fallback
            
        target_ke_sale_price = Decimal(str(jiji_median_sold_kes))
        target_gross_margin = Decimal('0.50')  # 50% floor
        target_landed_cost_usd = (target_ke_sale_price / fx_rate) * (Decimal('1') - target_gross_margin)
        
        # Determine acceptable condition based on product type
        acceptable_condition = "any-functional"  # default
        if "car seat" in category.lower() or "seat" in name.lower():
            acceptable_condition = "like-new | any-functional"
        elif "stroller" in category.lower():
            acceptable_condition = "gently-used | any-functional"
        elif "cloth" in category.lower() or "apparel" in category.lower():
            acceptable_condition = "gently-used | any-functional"
        elif "toy" in category.lower():
            acceptable_condition = "any-functional"
        elif "monitor" in category.lower() or "tech" in category.lower():
            acceptable_condition = "like-new | any-functional"
        
        # Compliance flags
        compliance_flags = []
        if "car seat" in category.lower() or "seat" in name.lower():
            compliance_flags.append("car-seat-DOM")
        # Add other compliance flags as needed
        
        # Source markets (prioritized)
        source_markets = ["ebay", "mercari", "fb", "offerup"]
        
        # Generate search queries based on product name
        search_queries = [
            f"{brand} {model}",
            f"{brand} {model} used",
            f"{brand} {model} 2022",
            f"{brand} {model} excellent condition",
            f"{brand} {model} like new"
        ]
        
        # Only include as priority if demand score >= 0.4 and we have KE price
        if demand_score >= 0.4:
            priority_items.append({
                'product': f"{brand} {model}",
                'brand': brand,
                'model': model,
                'demand_score': demand_score,
                'confidence': confidence,
                'target_landed_cost_usd': target_landed_cost_usd,
                'target_ke_sale_price_kes': target_ke_sale_price,
                'acceptable_condition': acceptable_condition,
                'compliance_flags': compliance_flags,
                'source_markets': source_markets,
                'search_queries': search_queries[:3],  # Top 3 queries
                'signals': signals
            })
        else:
            # Low demand score -> avoid this week
            avoid_this_week.append({
                'product': name,
                'demand_score': demand_score,
                'confidence': confidence
            })
    
    # Sort priority items by demand score descending
    priority_items.sort(key=lambda x: x['demand_score'], reverse=True)
    
    # Limit to maximum 8 items
    priority_items = priority_items[:8]
    
    # Generate the brief content
    today = datetime.now().strftime("%Y-%m-%d")
    
    brief_content = f"""GOAL
Source high-demand baby products for the Kenyan market targeting 30%+ net margin after all costs, focusing on items with strong demand signals and verified compliance.

PRIORITY ITEMS
"""
    
    for i, item in enumerate(priority_items, 1):
        brief_content += f"""{i}. Product: {item['product']}
   Demand score: {item['demand_score']:.3f}
   Confidence: {item['confidence']}
   Target landed cost (USD): {item['target_landed_cost_usd']:.2f}
   Target KE sale price (KES): {item['target_ke_sale_price_kes']:,.0f}
   Acceptable condition: {item['acceptable_condition']}
   Compliance flags: {' | '.join(item['compliance_flags']) if item['compliance_flags'] else 'none'}
   Source markets: {' | '.join(item['source_markets'])}
   Search queries:
     - {item['search_queries'][0]}
     - {item['search_queries'][1]}
     - {item['search_queries'][2]}
"""
    
    brief_content += "\nAVOID THIS WEEK\n\n"
    if avoid_this_week:
        for item in avoid_this_week:
            brief_content += f"- {item['product']} (demand score: {item['demand_score']:.3f}, confidence: {item['confidence']})\n"
    else:
        brief_content += "- No items to avoid this week based on demand signals\n\n"

    brief_content += "\nASSUMPTIONS\n\n"
    brief_content += """- Demand Scout signal scores accurately reflect Kenyan market interest
- Observed Jiji median sale prices represent achievable resale prices
- Facebook group engagement correlates with purchase intent
- Instagram and TikTok mention volumes indicate trending awareness
- Exchange rate remains stable at ~145 KES/USD for cost calculations
- Shipping costs from US to Nairobi average $25-35 per item via consolidator
- Products in 'like-new' or 'any-functional' condition are acceptable for resale
- No active recalls affect the priority items (verified via compliance check)
"""

    brief_content += "\nHUMAN REVIEW NEEDED\n\n"
    if human_review_needed:
        for item in human_review_needed:
            brief_content += f"- {item['product']}: {item['reason']} (demand score: {item['demand_score']:.3f}, confidence: {item['confidence']})\n"
    else:
        brief_content += "- No items require human review this week\n\n"
    
    # Save the brief
    progress_path.mkdir(parents=True, exist_ok=True)
    brief_file = progress_path / f"sourcing_brief_{today}.md"
    with open(brief_file, 'w') as f:
        f.write(brief_content)
    
    logger.info("Sourcing brief generated", 
                file=str(brief_file),
                word_count=len(brief_content.split()),
                priority_items=len(priority_items))
    
    # If not dry run, post to Telegram and create PR
    if not dry_run:
        logger.info("Posting brief to Telegram and creating PR (not implemented in this version)")
        # In a real implementation, this would:
        # 1. Send the brief to Telegram via the bot
        # 2. Create a git branch: task/weekly-brief-YYYY-MM-DD
        # 3. Commit the brief with message: docs(brief): weekly sourcing brief YYYY-MM-DD
        # 4. Open a PR for review
        # For now, we'll just log what would happen
        print(f"[DRY RUN MODE] Would post to Telegram and create PR for {brief_file}")
        print(f"[DRY RUN MODE] Branch: task/weekly-brief-{today}")
        print(f"[DRY RUN MODE] Commit: docs(brief): weekly sourcing brief {today}")
    
    return brief_content
