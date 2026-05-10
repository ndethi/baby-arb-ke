<!-- Skill version: 0.1 | Last improved: 2026-05-10 | Uses: 0 -->

# Sourcing Scout

Find candidate listings on US marketplaces matching a sourcing brief.

## When to use
- Trend PM has produced a weekly brief
- Watson sends: "Find me a NUNA PIPA under $X", "Search ebay for..."
- Daily watch on saved high-priority items for price drops

## Instructions
1. Read SOUL.md and the active sourcing brief.
2. For each priority item in the brief, run searches via:
   - eBay Browse API (MVP — only this in shadow pilot)
   - Mercari, FB Marketplace, OfferUp (post-MVP, via Apify)
3. Apply hard filters:
   - listing_price + us_shipping <= target_landed_cost / 2 (rough sanity)
   - condition matches brief acceptable_condition
   - seller_feedback_count >= 50 AND feedback_pct >= 98
   - shipping to US warehouse address available
4. For each candidate, extract a `BuyCandidate`:
   - listing_url, listing_price_usd, us_shipping_usd
   - brand, model, condition_text, condition_normalized
   - estimated_weight_lb (from listing or product DB lookup)
   - estimated_dimensions_in
   - origin_state, seller_id, seller_feedback
   - photos[] (URLs)
   - listing_ends_at (if auction)
5. For car seats: explicitly try to extract date-of-manufacture from
   listing description and photos. Pass photos URLs to Compliance for
   visual verification.
6. Pass each candidate through Compliance Checker. Drop BLOCK candidates
   immediately.
7. Pass remaining candidates through Pricing Engineer.
8. Output a ranked list of (candidate, compliance_verdict, pricing_verdict)
   triples sorted by margin descending, then by listing_ends_at ascending.

## Constraints
- Never bid or buy. Only return candidates.
- Never store full seller PII — only seller_id and aggregate feedback.
- Respect eBay API rate limits. Use tenacity with exponential backoff.
- Never use scraped sources without rotating user agents and respecting
  robots.txt.
- Drop listings shipping only within US (cannot reach our warehouse).
- Drop listings from sellers blocked in our deny list.

## Output format
```json
{
  "brief_id": "2026-W19",
  "generated_at": "2026-05-10T08:00:00Z",
  "candidates": [
    {
      "candidate": { ...BuyCandidate fields... },
      "compliance": { ...ComplianceVerdict... },
      "pricing": { ...PricingVerdict... },
      "rank": 1
    }
  ],
  "stats": {
    "searched": 42,
    "compliance_blocked": 5,
    "pricing_skipped": 18,
    "buy_recommended": 6,
    "review_required": 3
  }
}
```

## Commit format
`sourcing(<scope>): <description>`

Examples:
```
sourcing(ebay): handle item-not-shippable-internationally edge case
sourcing(filters): tighten seller feedback threshold to 98%
```

## Self-improvement signals
- If pricing_skipped rate exceeds 70%, the brief's target landed cost
  is too low — flag back to Trend PM.
- If a recall slips through (caught by Compliance Checker only after
  buy approval): add a pre-Compliance hard-block list keyed on known
  recalled SKUs.
- If candidates with high pricing rank later return for damage: add
  a condition-text NLP filter for words like "stained", "broken zip",
  "missing parts" that condition_normalized currently misses.
