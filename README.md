# baby-arb-ke

US-to-Kenya arbitrage pipeline for used baby items, run by a managed
team of AI agents on the [agentic-dev-team-framework](docs/agentic_dev_team_framework.md).

**Status:** MVP — pre-shadow-pilot. Not yet purchasing real inventory.

## What this is

A Python codebase plus an agent team that:

1. **Listens** to Kenyan demand signals (Jiji listings, FB parenting
   groups, IG/TikTok, Jumia stockouts) to identify which baby items
   have local pull this week.
2. **Sources** matching candidates from US marketplaces (eBay primary).
3. **Prices** every candidate through a deterministic landed-cost engine
   that enforces a 50% gross margin floor.
4. **Checks** every candidate against CPSC recalls, car-seat date-of-
   manufacture rules, and KEBS import restrictions.
5. **Recommends** weekly buys via Telegram with one-tap human approval.
6. **Buys**, ships, lists, and sells — with margin reconciliation after
   each sale to improve the model.

## Why an MVP repo

This is a portable scaffold. Drop it into your dev folder, point it at
a remote repo, and you have:

- Hermes-ready SOUL.md and 10 SKILL.md role definitions
- A working Python package skeleton with the three core engines
  (pricing, compliance, sourcing) stubbed and tested
- Conventional Commits + commitizen + commitlint enforcement
- GitHub Actions for commit linting and changelog automation
- A PR template with an agent-readable checklist
- Copilot cloud agent profiles mirroring the Hermes team

## MVP scope (first 4 weeks)

The MVP runs in **shadow mode** — it makes recommendations, you decide,
no real money moves. The goal is to calibrate the pricing model against
real KE sale outcomes before committing capital.

In scope:
- eBay Browse API integration (no Mercari/FB scraping yet)
- Landed-cost calculator with DHL Express + KE customs math
- CPSC recall lookup
- Car seat DOM parser
- Manual demand signal entry (you tell Hermes what's hot, it scores it)
- Weekly Telegram brief
- Margin Evaluator that compares predicted to actual after you log sales

Out of scope until shadow pilot validates margin discipline:
- Mercari, FB Marketplace, OfferUp scrapers
- Automated demand scraping (Apify/Phyllo)
- Auto-purchase rails (Mastercard Agent Pay / virtual card automation)
- Storefront integration (Shopify, Jiji API)

## Quickstart

```bash
# Clone and install
git clone git@github.com:ndethi/baby-arb-ke.git
cd baby-arb-ke
poetry install
poetry shell

# Set up env
cp .env.example .env
# Edit .env with your eBay App ID and other keys

# Enable the committed git hooks (commit-msg format, pre-push gate record)
git config core.hooksPath .githooks

# Run tests
pytest

# Run the CLI smoke test
baby-arb price --listing-url "https://www.ebay.com/itm/EXAMPLE"
baby-arb compliance check --upc 123456789012
baby-arb brief weekly --dry-run
```

## Before you push

Every push goes through one gate, and every branch keeps a prompt log:

```bash
scripts/pre_push.sh      # branch, commits, hygiene, ruff, pytest, bandit, secrets, pip-audit, prompt log
git add docs/audit/gates/<branch-slug>.md
git commit -m "chore(audit): record pre-push gate for <sha>"
git push                 # the pre-push hook refuses a push with no PASS record
```

See [docs/audit/README.md](docs/audit/README.md) and the skills in
[docs/skills/dev-lifecycle](docs/skills/dev-lifecycle/SKILL.md),
[pre-push](docs/skills/pre-push/SKILL.md) and [release](docs/skills/release/SKILL.md).

## Deploy as a Hermes project

```bash
# Bootstrap message to Hermes on Telegram (after pushing repo to GitHub):
"""
Set up the agentic dev team for a new project.
Project: baby-arb-ke
Repo: github.com/ndethi/baby-arb-ke

1. Read SOUL.md and AGENTS.md from the repo root.
2. Load all skill files from docs/skills/.
3. Install commitizen: pip install commitizen
4. Set up the daily docs-sync cron at 8pm UTC.
5. Set up the weekly Curator run at 7pm UTC Sunday.
6. Set up the weekly Sourcing Brief at 6am UTC Monday.
7. Write memory: this project uses the agentic-dev-team framework
   for a US→KE arbitrage business. The pricing engine has veto
   power. Never auto-buy above $200.
8. Confirm setup on Telegram with a summary.
"""
```

## How the agent team works

See [docs/architecture.md](docs/architecture.md) for the full picture.
The short version:

```
[Demand Scout] ──► weekly KE signal scores
       │
       ▼
[Trend PM] ──► sourcing brief: "find these 8 items this week"
       │
       ▼
[Sourcing Scout] ──► candidates from eBay matching brief
       │
       ▼
[Compliance Checker] ──► hard veto on recalls, expired car seats
       │
       ▼
[Pricing Engineer] ──► landed cost + margin verdict (>= 50% or skip)
       │
       ▼
[Telegram brief to Watson] ──► one-tap approval per item
       │
       ▼ (after approval)
[Buyer] ──► virtual card purchase
       │
       ▼
[Logistics Coordinator] ──► warehouse → DHL → Nairobi
       │
       ▼
[Listing Writer] ──► Jiji + IG + storefront listings
       │
       ▼ (after sale)
[Margin Evaluator] ──► reconcile predicted vs actual, feed back to skills
```

## Documentation

- [Architecture overview](docs/architecture.md)
- [Landed-cost model](docs/landed_cost_model.md) — the pricing formula
- [Compliance rules](docs/compliance_rules.md) — recall, DOM, KEBS
- [Demand signals](docs/demand_signals.md) — what we score and why
- [Operating runbook](docs/operating_runbook.md) — weekly/daily/monthly
- [Agentic dev team framework](docs/agentic_dev_team_framework.md) — parent framework

## License

Private. All rights reserved.
