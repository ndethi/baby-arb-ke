<!-- Skill version: 0.1 | Last improved: 2026-05-10 | Uses: 0 -->

# Pricing Engineer

Run the deterministic landed-cost calculation on a candidate listing
and return a buy verdict with full margin breakdown. Has veto power
over every buy decision.

## When to use
- Sourcing Scout has produced a candidate
- Watson sends: "Price this listing: <url>", "What's the margin on..."
- Compliance Checker has returned PASS or REVIEW (never run on BLOCK)
- Any case where a margin number is needed for a buy decision

## Instructions
1. Read SOUL.md and `docs/landed_cost_model.md` in full before any change
   to formula or weights. The math is the spine of the business.
2. Receive input as a `BuyCandidate` with at minimum:
   - listing_url, listing_price_usd, listing_shipping_to_us_warehouse_usd
   - item_brand, item_model, item_condition
   - estimated_weight_lb, estimated_dimensions_in (length, width, height)
   - origin_state (US state of seller for sales tax)
   - reference_ke_sale_price_kes (median from Demand Scout)
3. Run `pricing.calculate_landed_cost(candidate)` from
   `src/baby_arb/pricing/engine.py`. This returns a `LandedCost` with:
     listing_price_usd
     us_shipping_usd
     us_sales_tax_usd        (origin_state lookup)
     warehouse_handling_usd  (consolidator per-item fee)
     international_shipping_usd  (DHL/Aramex/sea by weight + dim)
     ke_customs_duty_kes     (25% of CIF)
     ke_vat_kes              (16% of CIF + duty)
     ke_idf_kes              (3.5% of CIF)
     ke_rdl_kes              (2% of CIF)
     ke_last_mile_kes
     fx_rate_used
     fx_rate_age_hours
     total_landed_cost_kes
     confidence              (HIGH | MEDIUM | LOW)
4. Compute margin: `(reference_ke_sale_price_kes - total_landed_cost_kes)
   / total_landed_cost_kes`.
5. Return a `PricingVerdict`:
     BUY      if margin >= MARGIN_FLOOR_PCT and confidence >= MEDIUM
     ABSTAIN  if confidence == LOW
     SKIP     if margin < MARGIN_FLOOR_PCT
     REVIEW   if margin between floor and floor+5pp (close to floor)
6. Include a one-paragraph human-readable explanation that names the
   single biggest cost driver and the slimmest margin assumption.
7. If running in IDE/code-edit mode (changing the engine itself):
   regression-test against `tests/fixtures/landed_cost_cases.json`
   before opening PR. Any case that flips verdict requires PR
   commentary explaining why.

## Constraints
- Never modify MARGIN_FLOOR_PCT inline. It lives in `pricing/rules.py`
  and is the only source of truth.
- Never call an LLM inside the calculation path. Pure Python only.
- Never silently coerce missing inputs. Missing weight → confidence LOW.
- Never use a stale FX rate (>24h). Refresh before calculation.
- Never round intermediate values. Round only the final display.
- Never blend "fees" into one number. Every component is named.

## Output format
A `PricingVerdict` JSON document:
```json
{
  "verdict": "BUY | SKIP | ABSTAIN | REVIEW",
  "margin_pct": 53.4,
  "margin_kes": 12450,
  "total_landed_cost_kes": 23300,
  "reference_ke_sale_price_kes": 35750,
  "confidence": "HIGH | MEDIUM | LOW",
  "biggest_cost_driver": "international_shipping_usd",
  "slimmest_assumption": "estimated weight 8.5 lb (no scale data)",
  "explanation": "One paragraph for human review.",
  "breakdown": { ...all LandedCost fields... },
  "calculated_at": "2026-05-10T12:00:00Z",
  "fx_rate_used": 145.3,
  "fx_rate_age_hours": 2.1
}
```

## Commit format
`pricing(<scope>): <description>`

Examples:
```
pricing(landed-cost): add IDF fee to CIF calculation
pricing(rules): clarify confidence thresholds for missing weight
pricing(fx): cache exchange rate with 12h TTL
```

## Self-improvement signals
- If Margin Evaluator reports actual margin diverged from predicted
  by more than 10% on 3+ items in a week, the model has drifted.
  Update step 3 of the engine — usually a missing fee or stale rate.
- If "ABSTAIN" rate exceeds 30% of candidates, weight estimation is
  too conservative. Tighten the LOW confidence trigger.
- If items pass with BUY verdict but Compliance later catches a
  recall, add the Compliance gate as a precondition (it should
  already be there — bug if not).
