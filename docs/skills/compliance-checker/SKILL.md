<!-- Skill version: 0.1 | Last improved: 2026-05-10 | Uses: 0 -->

# Compliance Checker

Hard veto layer on every buy candidate. Checks CPSC recalls, car seat
date-of-manufacture, KEBS-restricted items, and brand authenticity.
Returns one of PASS, BLOCK, REVIEW — no other states.

## When to use
- Sourcing Scout has produced a candidate
- Before any Pricing Engineer run (Pricing skips on BLOCK)
- Watson sends: "Check this listing for recalls", "Is this car seat OK"
- Daily refresh of the CPSC recall cache

## Instructions
1. Read SOUL.md and `docs/compliance_rules.md` before any change.
2. Receive a `BuyCandidate` and run the gate sequence in order. The
   first BLOCK verdict short-circuits — do not run later checks:

   STEP 1 — CPSC recall check
     - Look up the item by brand + model + UPC if available
     - If listed as recalled in CPSC SaferProducts: BLOCK
     - If brand+model has had any recall in last 5 years on related
       SKU: REVIEW (let human judge if this specific unit is affected)
     - Cache TTL 24h. If cache stale, force refresh. If refresh fails
       (network, API down): fail closed with REVIEW + reason "cpsc_unreachable"

   STEP 2 — Car seat date-of-manufacture check
     - Applies if item_category == "car_seat"
     - Parse DOM from listing description, photos (label visible), or
       seller-confirmed message
     - If DOM not findable: REVIEW with reason "dom_not_visible"
     - If now() - DOM > 6 years: BLOCK with reason "dom_expired"
     - If now() - DOM > 5 years: REVIEW with reason "dom_near_expiry"

   STEP 3 — KEBS-restricted items check
     - Load `data/fixtures/kebs_restricted.json`
     - If item matches any restricted category by HS code or product
       type: BLOCK with reason "kebs_restricted"

   STEP 4 — Counterfeit-prone brand check
     - Brands with known counterfeit issues: NUNA, UPPAbaby, Stokke,
       BabyBjörn, Doona, Cybex
     - If brand on list AND seller has < 50 feedback OR feedback < 98%:
       REVIEW with reason "auth_seller_risk"
     - If brand on list AND no clear photos of branding/labels:
       REVIEW with reason "auth_photos_missing"

   STEP 5 — Generic safety flags
     - Drop-side cribs (banned in US since 2011): BLOCK
     - Inclined sleepers (Rock 'n Play class, banned 2019): BLOCK
     - Boppy newborn loungers (recalled 2021): BLOCK
     - Walkers with caster wheels meeting deprecated standard: BLOCK

3. Return a `ComplianceVerdict`:
```json
{
  "verdict": "PASS | BLOCK | REVIEW",
  "reasons": ["dom_expired", "..."],
  "checks_run": ["cpsc", "carseat_dom", "kebs", "auth", "safety"],
  "checks_skipped": [],
  "cache_age_hours": 2.1,
  "checked_at": "2026-05-10T12:00:00Z"
}
```

4. Never call Pricing Engineer on BLOCK. Always call on PASS. On
   REVIEW, post to Telegram for human decision before Pricing.

## Constraints
- Never loosen a BLOCK verdict in code. New BLOCK conditions can be
  added freely; removal requires explicit human approval in PR.
- Never trust a CPSC cache older than 24 hours.
- Never write the cache to a path outside `data/cache/`.
- Never store seller PII in logs or cache.
- Default to fail-closed on every uncertainty.

## Output format
`ComplianceVerdict` JSON as shown above.

## Commit format
`<type>(compliance): <description>`

Examples:
```
fix(compliance): handle CPSC API timeout with stale-cache fallback
data(compliance): refresh KEBS restricted list 2026-05
feat(compliance): add Doona infant car seat recall handling
```

## Self-improvement signals
- If a recall is announced and we already approved an item from that
  product line in the last 30 days: incident review. Update step 1
  to expand the related-SKU lookup window.
- If REVIEW rate exceeds 40% of candidates, the rules are too loose
  on triggers. Tighten conditions to either PASS or BLOCK more often.
- If counterfeit complaints surface from KE buyers on a brand not in
  step 4: add it.
- If KEBS rejects a shipment for a restricted item we missed: update
  `kebs_restricted.json` and add a regression test.
