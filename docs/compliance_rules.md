# Compliance Rules

The hard veto layer. Every rule here is non-negotiable — Compliance
Checker fails closed on any uncertainty.

## CPSC recall check

The US Consumer Product Safety Commission maintains a public recall
database queryable via the SaferProducts API.

**Lookup strategy:**
1. Exact match on UPC if available
2. Brand + model substring match
3. Product category + manufacturer match for fuzzy cases

**Verdict logic:**
- Listed in current recalls → BLOCK
- Brand+model had any recall in last 5 years → REVIEW (human checks
  if this specific unit is the recalled production run)
- API unreachable AND cache stale → REVIEW with reason `cpsc_unreachable`
- API unreachable AND cache fresh → use cache, note staleness

**Cache:** 24h TTL maximum. Persists at `data/cache/cpsc/recalls.json`.

**Daily refresh:** A cron job at 04:00 UTC pulls all baby/infant
category recalls and warms the cache.

## Car seat date-of-manufacture

Car seats have a hard expiry date set by the manufacturer, typically
6-10 years from date of manufacture. After this date the plastic
degrades and the seat may not perform in a crash.

**Operating ceiling: 6 years from DOM.** Even if the manufacturer
states 10, the import + resale + use cycle eats 1-2 years easily.
We will not sell a seat that has less than 4 years of usable life
remaining at point of sale.

**DOM extraction:**
1. Listing description scan for date patterns (regex)
2. Photo OCR on the manufacturer label (post-MVP)
3. Seller message asking for label photo if not visible

**Verdict logic:**
- DOM not findable → REVIEW with reason `dom_not_visible`
- DOM > 6 years from now() → BLOCK with reason `dom_expired`
- DOM > 5 years → REVIEW with reason `dom_near_expiry` (allow only if
  KE buyer use case is short-term and this is disclosed in listing)
- DOM ≤ 5 years → PASS this check

## KEBS-restricted items

The Kenya Bureau of Standards restricts or requires special
certification for certain imports. Some baby items fall into
restricted categories.

**Stored at:** `data/fixtures/kebs_restricted.json`

**Categories that need attention:**
- Mattresses (require KEBS PVoC certification)
- Electrical baby items (sterilisers, monitors with mains power)
- Items with lithium batteries (specific routing rules)
- Toys with paint/finish (lead content tested)

**Verdict logic:**
- Match against restricted list → BLOCK with `kebs_restricted` reason
- Match against requires-certification list → REVIEW with reason

## Counterfeit-prone brands

Brands with known fake/counterfeit market presence. Extra signals
required before PASS.

**List (extend as we learn):**
- NUNA (PIPA, Mixx, RAVA, DEMI seats)
- UPPAbaby (Vista, Cruz strollers)
- Stokke (Tripp Trapp, Xplory)
- BabyBjörn (carriers, bouncers)
- Doona (car seat strollers — high counterfeit rate)
- Cybex (Cloud Z, Sirona, Priam)

**Required signals if brand on list:**
- Seller feedback ≥ 50 transactions
- Seller feedback rate ≥ 98%
- Photos showing branding labels, not stock photos
- Price not absurdly low (>30% below median used = suspicious)

**Verdict logic:**
- Any signal fails → REVIEW with specific reason
- Multiple fail → BLOCK with `auth_high_risk`

## Static safety blocks

Items on this list are never bought, regardless of any other signal.

| Item type | Why | Status |
|-----------|-----|--------|
| Drop-side cribs | Banned in US since 2011 | BLOCK |
| Inclined sleepers (any) | Banned 2019, multiple deaths | BLOCK |
| Boppy newborn loungers | Recalled 2021, eight deaths | BLOCK |
| Infant slings of certain designs | Suffocation risk | BLOCK |
| Walkers with caster wheels | Old standard, banned in CA/NY/etc | BLOCK |
| Bumbo seats with no restraint | Recalled 2012 | BLOCK |
| Fisher-Price Rock 'n Play | Recalled 2019 | BLOCK |

This list is loaded from `data/fixtures/safety_blocks.json` and is
checked first in the gate (cheapest filter).

## Order of checks (cheapest first)

1. Static safety blocks (in-memory list, O(1))
2. Car seat DOM if applicable (regex on listing text)
3. Counterfeit signals if brand on list (in-memory + listing inspection)
4. KEBS restricted (file lookup)
5. CPSC recall (API or cache, slowest)

If any step returns BLOCK, short-circuit. If any returns REVIEW,
continue (collect all REVIEW reasons), final verdict is REVIEW.
Only if all return PASS is verdict PASS.

## Failure modes and responses

| Failure | Response |
|---------|----------|
| CPSC API down, cache fresh | Use cache, log staleness |
| CPSC API down, cache stale | REVIEW with reason `cpsc_unreachable` |
| KEBS file missing | Hard error — refuse to run gate |
| Brand list corrupted | Hard error — refuse to run gate |
| DOM regex fails on a known good listing | REVIEW + log for rule update |

## Audit trail

Every gate call writes a record to `compliance_verdicts` table with:
- input candidate hash
- verdict
- reasons
- checks_run
- checks_skipped (if short-circuited)
- cache ages
- timestamp

This lets Margin Evaluator and post-hoc reviewers reconstruct exactly
why any decision was made.

## Updating the rules

| Change | Approval needed |
|--------|----------------|
| Add a new BLOCK condition | None — defaults safer |
| Add a new REVIEW trigger | None — defaults safer |
| Tighten an existing rule | None |
| Loosen an existing BLOCK | Watson approval in PR |
| Remove a check entirely | Watson approval + 30-day deprecation |
| Refresh KEBS list | Standard PR |
| Refresh CPSC cache | Automated, no PR |
