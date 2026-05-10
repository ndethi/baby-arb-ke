# Hermes Handoff Notes

This document is the bridge between the MVP repo as shipped and a fully
operational pipeline. Everything in here is meant for Hermes (or you,
or a Copilot cloud agent) to pick up and finish.

The MVP that ships is intentionally sharp:
- Pricing engine is **complete and working** — pure Python, deterministic,
  fully tested. It refuses to lie about margin even on items you want to like.
- Compliance gate is **complete and working** — multi-layer veto with
  fail-closed defaults and full test coverage.
- Demand aggregator is **complete** for manual signal entry.
- CLI smoke commands run end-to-end without network.

What's intentionally stubbed: live marketplace clients, the buyer flow,
logistics tracking, listing publishing, and persistence. These are the
items below.

## Priority order

The order matters — earlier items unblock later ones.

### 1. Sourcing Scout — eBay Browse API client (1-2 days)

**Build location:** `src/baby_arb/sourcing/ebay/`

**Files:**
- `client.py` — async httpx client with OAuth2 client-credentials,
  tenacity retry, rate limit handling
- `parser.py` — eBay item JSON → `BuyCandidate`
- `search.py` — turn a `SourcingBrief` priority item into a Browse
  API query with hard filters
- `runner.py` — `run_brief(brief) -> list[(candidate, compliance, pricing)]`

**Hermes prompt:**
```
Build src/baby_arb/sourcing/ebay/ following docs/skills/sourcing-scout/SKILL.md.
Use the eBay Browse API. OAuth2 client-credentials. httpx async. tenacity
retry on 5xx with exponential backoff. Parse listings into BuyCandidate
per src/baby_arb/models/candidate.py. Apply the hard filters from
SKILL.md step 3. Skip listings that don't ship internationally. Tests
mock the eBay API with respx fixtures.
```

### 2. Storage layer (1 day)

**Build location:** `src/baby_arb/storage/`

**Files:**
- `db.py` — SQLModel engine, session context manager
- `tables.py` — tables for briefs, candidates, pricing_verdicts,
  compliance_verdicts, purchases, sales, margin_evaluations
- `repo.py` — one function per use case (save_pricing_verdict,
  get_completed_sales_since, etc.)

**Hermes prompt:**
```
Build src/baby_arb/storage/ with SQLModel. Tables match the data
classes in src/baby_arb/models/. SQLite for dev, Postgres-compatible.
Migrations via alembic. Repo functions are thin wrappers — no business
logic in the storage layer.
```

### 3. Demand Scout scrapers (2-3 days)

**Build location:** `src/baby_arb/demand/`

**Files:**
- `jiji.py` — Apify-backed Jiji listings scraper (active count,
  sold count, median sold price)
- `jumia.py` — product page check for stock status
- `phyllo.py` — IG/TikTok creator coverage
- `fb_groups.py` — FB parenting group sentiment (manual entry first,
  scraper later)

**Hermes prompt:**
```
Build src/baby_arb/demand/jiji.py using Apify. Tests use a captured
Jiji response fixture. Output normalised to DemandSignals. Same pattern
for jumia.py and the others. Phyllo first checks if API key exists;
if not, returns UNKNOWN with a note.
```

### 4. Trend PM — weekly brief composer (1 day)

**Build location:** `src/baby_arb/orchestration/brief.py`

**Hermes prompt:**
```
Build the weekly brief composer per docs/skills/trend-pm/SKILL.md.
Reads the latest demand_scout cache, last 4 weeks of margin_evaluations,
composes a 3-8 item priority list, writes to docs/progress/sourcing_brief_*.md,
posts to Telegram with inline buttons.
```

### 5. Telegram integration (0.5 day)

**Build location:** `src/baby_arb/integrations/telegram.py`

**Hermes prompt:**
```
Build a thin Telegram client using python-telegram-bot or aiogram.
Wraps: post_message(text), post_brief(brief), post_candidates(list).
Inline buttons for approve/decline. Webhook handler for callback queries.
Approval messages signed with a per-message HMAC so Buyer can verify.
```

### 6. Buyer agent (POST-shadow-pilot, 1-2 days)

**Build location:** `src/baby_arb/buyer/`

**Hermes prompt:**
```
Build the Buyer per docs/skills/buyer/SKILL.md. Wise Business virtual
card issuance. Marketplace Buy API or browser automation as fallback.
Hard preconditions: Approval token signature valid, Compliance PASS
age <24h, Pricing BUY age <4h, listing price unchanged. Per-task card
issuance, single-use, exact-amount + 5% buffer, merchant-locked.
```

This one is post-shadow-pilot. Don't activate until 4+ weeks of
margin reconciliation has validated the pricing model on real KE outcomes.

### 7. Logistics Coordinator (POST-buyer, 1-2 days)

**Build location:** `src/baby_arb/logistics/`

**Hermes prompt:**
```
Build per docs/skills/logistics-coordinator/SKILL.md. DHL Express API
for booking + tracking. Warehouse webhook handler for intake (actual
weight, dims, photos). Re-trigger Pricing Engineer if actual weight
differs >15% from estimate. Customs invoice generation.
```

### 8. Margin Evaluator (concurrent with sales) (0.5 day)

**Build location:** `src/baby_arb/orchestration/margin_eval.py`

**Hermes prompt:**
```
Build per docs/skills/margin-evaluator/SKILL.md. Reconciles actual sale
margin against Pricing Engineer's prediction. Categorises ON-TARGET,
SLIGHT, OFF. Identifies cost drivers responsible for OFF items.
Aggregates weekly stats per category. Writes to docs/progress/margin_eval_*.md
and Telegram summary.
```

### 9. Listing Writer (post-first-shipment, 1 day)

**Build location:** `src/baby_arb/listings/`

Per `docs/skills/listing-writer/SKILL.md`. Three variants per item:
Jiji, Instagram, storefront.

## Bootstrap message for Hermes

When the repo is on GitHub, send this exact message to Hermes on Telegram:

```
Set up the agentic dev team for a new project.
Project: baby-arb-ke
Repo: github.com/{{REPO_OWNER}}/baby-arb-ke

1. Read SOUL.md and AGENTS.md from the repo root.
2. Load all skill files from docs/skills/.
3. Read docs/architecture.md, docs/landed_cost_model.md,
   docs/compliance_rules.md, docs/operating_runbook.md.
4. Verify the test suite passes: cd baby-arb-ke && pytest
5. Install commitizen: pip install commitizen
6. Set up the daily docs-sync cron at 8pm UTC.
7. Set up the weekly Curator run at 7pm UTC Sunday.
8. Set up the weekly Sourcing Brief at 6am UTC Monday.
9. Read docs/HERMES_HANDOFF.md for the build queue.
10. Write memory: this project uses the agentic-dev-team framework
    for a US→KE arbitrage business. The pricing engine has veto power.
    Never auto-buy above $200.
11. Confirm setup on Telegram with a summary including:
    - Test count and pass rate
    - Which skills are loaded
    - Which build queue items are unblocked
    - Suggested first task
```

## Calibration before any real money

Even after Hermes finishes the build queue, do not commit capital until:

1. **Shadow pilot complete (4+ weeks).** Hermes recommends, you decide
   manually, no buys. Compare predicted margin to observed Jiji clearing
   prices for 20+ items.
2. **Pricing drift under 10pp** in shadow pilot reconciliation.
3. **Compliance has caught at least one real recall** in shadow data
   (test the gate is actually working).
4. **Demand Scout signals predict** sell-through on items you've already
   sold via your existing channels (if any).
5. **Money-flow checks pass** per `docs/operating_runbook.md` final section.

The pricing math from the worked example in `docs/landed_cost_model.md`
shows clearly that not every "obvious" arbitrage is real. **The whole
point of this system is to make those failures cheap and visible
before the money moves.**

## Skill versioning during development

When Hermes (or you) modifies a SKILL.md, bump the version comment:
```
<!-- Skill version: 0.2 | Last improved: 2026-MM-DD | Uses: N -->
```

The Curator increments `Uses` automatically. Manual edits should
increment the version digit.

## Common mistakes to avoid

1. **Don't add "fees" as a single line item.** Every cost is named.
2. **Don't bypass Compliance to "test pricing".** Pricing should never
   be reachable without Compliance PASS in production paths. Tests are
   fine — they call the engine directly.
3. **Don't change MARGIN_FLOOR_PCT in an inline edit.** It lives in
   `pricing/rules.py` and changing it requires SOUL.md update + human
   approval.
4. **Don't write code that hits live eBay/Jiji/etc in tests.** Use
   respx fixtures.
5. **Don't store the FX rate in two places.** It comes from `pricing/fx.py`
   with TTL cache. The engine reads age and decides confidence.
