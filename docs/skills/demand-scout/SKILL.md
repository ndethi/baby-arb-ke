<!-- Skill version: 0.1 | Last improved: 2026-05-10 | Uses: 0 -->

# Demand Scout

Aggregate Kenyan demand signals into a structured score per candidate
product or category.

## When to use
- Cron-triggered Sunday 18:00 UTC, output feeds Trend PM at Monday 06:00 UTC
- Watson sends: "What's hot in KE this week", "Is there demand for X"
- Trend PM requests a fresh signal report

## Instructions
1. Read SOUL.md and `docs/demand_signals.md`.
2. For each candidate product (or category if no candidate yet):
   STEP 1 — Marketplace supply/demand on Jiji.co.ke
     - active_listings_count (current)
     - sold_listings_30d (from listing history)
     - median_listed_price_kes
     - median_sold_price_kes (where visible)
   STEP 2 — Retail availability
     - Jumia: in stock / out of stock / not listed
     - Kilimall: in stock / out of stock / not listed
     - If out of stock for 2+ weeks: strong demand signal
   STEP 3 — Social signals
     - Kenyan parenting Facebook groups: mentions in last 30d, intent score
       (recommendations, "where can I get", "anyone selling")
     - Instagram: Kenyan mom creators tagging the brand/product, 30d count
     - TikTok: Kenyan parent creators featuring the product, 30d count
     - Note: weight FB groups 3x IG/TikTok for purchase intent
   STEP 4 — Price discovery
     - Pigiame search frequency for the product term
     - Average asking price across visible KE listings
3. MVP mode: signals are entered manually by Watson via CLI or Telegram.
   Future: Apify scrapers for Jiji + Phyllo for IG/TikTok creator data.
4. Compute composite `demand_score` 0.0-1.0 with weights from
   `src/baby_arb/demand/weights.py`. Never invent missing data — mark
   the data point as UNKNOWN and lower confidence accordingly.
5. Output a structured signal report per product, save to
   `data/cache/demand_scout/latest.json` and a dated copy.

## Constraints
- Never invent KE retail or used prices. UNKNOWN beats fabricated.
- Never weight TikTok/IG higher than FB groups for intent.
- Never store individual creator PII — aggregate counts only.
- Manual MVP signals: log who entered them and when (audit trail).

## Output format
```json
{
  "generated_at": "2026-05-10T18:00:00Z",
  "products": [
    {
      "name": "NUNA PIPA infant car seat",
      "demand_score": 0.78,
      "confidence": "MEDIUM",
      "signals": {
        "jiji_active_listings": 3,
        "jiji_sold_30d": 11,
        "jiji_median_sold_kes": 32500,
        "jumia_stock": "out_4w",
        "fb_group_mentions_30d": 23,
        "fb_group_intent_score": 0.71,
        "ig_kenyan_mentions_30d": 47,
        "tiktok_kenyan_mentions_30d": 8
      },
      "missing_data": ["pigiame_volume"],
      "recommendation": "PURSUE — limited supply, active demand"
    }
  ]
}
```

## Commit format
`data(demand): manual signal entry YYYY-MM-DD` (for manual entries)
`feat(demand): add Jiji scraper integration` (for code)

## Self-improvement signals
- If items with demand_score > 0.7 fail to sell within 45 days, the
  weights are wrong. Run a regression to find which signals correlate
  with actual sale velocity and recalibrate.
- If FB groups produce too few signals (under 5/week): expand the
  group list or check scraper health.
