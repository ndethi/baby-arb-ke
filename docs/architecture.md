# Architecture

## System overview

```
┌──────────────────────────────────────────────────────────────────┐
│                      WEEKLY CYCLE (Mon-Sun)                       │
└──────────────────────────────────────────────────────────────────┘

Sun 18:00 UTC ─► Demand Scout
                 ├── Jiji marketplace scrape (post-MVP)
                 ├── Jumia/Kilimall stock check
                 ├── FB parenting groups (post-MVP, manual in MVP)
                 ├── IG/TikTok creator counts (post-MVP)
                 └── Output: data/cache/demand_scout/latest.json

Mon 06:00 UTC ─► Trend PM
                 ├── Reads demand report + last 4w margin reports
                 ├── Composes weekly sourcing brief (3-8 items)
                 └── Posts to Telegram + opens PR

Mon 08:00 UTC ─► Sourcing Scout
                 ├── eBay Browse API search per priority item
                 ├── (post-MVP) Mercari, FB, OfferUp via Apify
                 ├── For each candidate:
                 │     ├── Compliance Checker (PASS/BLOCK/REVIEW)
                 │     └── Pricing Engineer (BUY/SKIP/ABSTAIN/REVIEW)
                 └── Ranked candidate list to Telegram

Mon-Sat        ─► Watson approves/declines candidates via Telegram
                 ├── (MVP) Manual approval, manual buy
                 └── (post-MVP) Buyer agent + virtual card flow

Continuous     ─► Logistics Coordinator (post-MVP)
                 ├── US warehouse intake → consolidation → DHL/Aramex
                 └── KE customs → last-mile

Continuous     ─► Listing Writer (post-MVP)
                 └── Jiji + IG + storefront listings

Sun 17:00 UTC ─► Margin Evaluator
                 ├── Reconciles actual vs predicted on completed sales
                 ├── Flags drift > 10pp
                 └── Reports to Telegram, opens issue if pattern detected
```

## Modules

### `src/baby_arb/pricing/`

The deterministic landed-cost engine. Pure Python, no LLM in the
calculation path. The single source of truth for `MARGIN_FLOOR_PCT`,
KE customs rates, and FX handling.

Key files:
- `engine.py` — `calculate_landed_cost(candidate) -> LandedCost`
- `rules.py` — constants: margin floor, customs rates, weight bands
- `fx.py` — exchange rate lookup with TTL cache
- `ke_customs.py` — duty + VAT + IDF + RDL on CIF
- `us_costs.py` — sales tax by state, warehouse handling, US shipping
- `intl_shipping.py` — DHL Express + Aramex rate cards by weight/dim
- `verdict.py` — `pricing_verdict(candidate, ref_price) -> PricingVerdict`

### `src/baby_arb/compliance/`

Hard veto layer. Fail-closed on uncertainty.

Key files:
- `gate.py` — `gate(candidate) -> ComplianceVerdict` (single entry)
- `cpsc.py` — CPSC SaferProducts API client + 24h cache
- `carseat.py` — DOM extraction + 6-year ceiling check
- `kebs.py` — KE-restricted items lookup
- `authenticity.py` — counterfeit-prone brand + seller signals
- `rules.py` — `CARSEAT_DOM_CEILING_YEARS`, brand lists, recall lookback

### `src/baby_arb/sourcing/`

Marketplace clients. eBay only in MVP.

Key files:
- `ebay/client.py` — Browse API client with retry/rate limit
- `ebay/search.py` — query builder from sourcing brief
- `ebay/parser.py` — listing → BuyCandidate normaliser
- `(post-MVP) mercari/`, `fb/`, `offerup/` — Apify-backed clients

### `src/baby_arb/demand/`

KE signal aggregation. Manual entry in MVP, scrapers post-MVP.

Key files:
- `aggregator.py` — composes `DemandReport` from raw signals
- `weights.py` — signal weights for composite score
- `(post-MVP) jiji.py`, `phyllo.py`, `fb_groups.py`

### `src/baby_arb/models/`

Pydantic v2 models, shared across modules.

Key models:
- `BuyCandidate`
- `LandedCost`
- `PricingVerdict`
- `ComplianceVerdict`
- `DemandSignals`
- `DemandReport`
- `SourcingBrief`

### `src/baby_arb/storage/`

SQLite for dev, Postgres for prod. SQLModel ORM.

Tables:
- `briefs` — weekly sourcing briefs
- `candidates` — every listing seen
- `pricing_verdicts` — every margin calculation
- `compliance_verdicts` — every recall/DOM check
- `purchases` — actual buys (post-MVP)
- `shipments` — logistics records (post-MVP)
- `sales` — KE-side sale events (post-MVP)
- `margin_evaluations` — predicted vs actual records

### `src/baby_arb/cli.py`

Typer-based CLI. Thin wrappers calling domain modules.

Commands:
- `baby-arb price --listing-url <url>` — single-candidate price check
- `baby-arb compliance check --upc <upc>` — recall/DOM check
- `baby-arb brief weekly` — generate weekly brief
- `baby-arb scout --brief-id <id>` — run sourcing
- `baby-arb eval margin` — run margin evaluator
- `baby-arb db init` — initialise SQLite

## Data flow

```
SourcingBrief ──► Sourcing Scout ──► [BuyCandidate, ...]
                                         │
                                         ▼
                                  Compliance Gate
                                  ├ BLOCK ─► dropped
                                  ├ REVIEW ─► Telegram for human
                                  └ PASS  ─► Pricing Engine
                                              │
                                              ▼
                                       LandedCost + Verdict
                                       ├ SKIP ─► dropped (low margin)
                                       ├ ABSTAIN ─► dropped (low confidence)
                                       ├ REVIEW ─► Telegram for human
                                       └ BUY  ─► Telegram for approval
                                                  │
                                                  ▼ (Watson approves)
                                            Buyer (post-MVP)
                                                  │
                                                  ▼
                                            Logistics Coord
                                                  │
                                                  ▼
                                            Listing Writer
                                                  │
                                                  ▼ (KE buyer pays)
                                            Margin Evaluator
                                                  │
                                                  ▼
                                            Updates pricing weights
                                            (the feedback loop)
```

## External dependencies

Required for MVP:
- eBay Developer App (Browse API)
- CPSC SaferProducts API (free, public)
- Telegram bot token
- FX rate provider (Open Exchange Rates or wise.com API)

Required for full operation (post-MVP):
- DHL Express API account
- Wise Business account
- M-Pesa Daraja credentials
- Apify or Bright Data subscription (for non-eBay scrapers)
- Phyllo or Modash (for IG/TikTok signal coverage)
- Jiji.co.ke posting credentials
- Shopify (for storefront)

## Design principles

1. **Deterministic core, intelligent shell.** The pricing math is pure
   Python. The LLM layer interprets, explains, and routes — never
   computes margin.

2. **Fail closed.** Compliance and Pricing default to abstain or block
   on uncertainty. Lost revenue from a missed buy is recoverable;
   margin loss from a bad buy is not.

3. **Veto, don't vote.** Pricing veto is binary. Compliance veto is
   binary. No "weighted" decisions where one component can drag a
   bad-margin item to BUY.

4. **Audit by default.** Every verdict is logged with inputs,
   timestamp, FX rate used, cache age. Margin Evaluator can replay
   any decision.

5. **Human gates at money.** Approval to spend > $200, approval to
   merge to main, approval to release a held shipment. Hermes proposes;
   Watson disposes.

6. **One brief per week.** Decision fatigue kills discipline. Weekly
   cadence forces batching, not constant attention.
