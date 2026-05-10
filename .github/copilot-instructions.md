# Copilot Instructions — baby-arb-ke

<!-- Read by GitHub Copilot in IDE and Copilot cloud agents. -->
<!-- Augments AGENTS.md and SOUL.md — read those first. -->

## Always read first

1. `SOUL.md` — project identity and hard constraints
2. `AGENTS.md` — universal agent entry point
3. `docs/skills/<your-role>/SKILL.md` — your role's behaviour spec

## Project tl;dr

Python pipeline for sourcing used baby items from US marketplaces and
reselling in Kenya at 50%+ gross margin. Pricing engine and compliance
checker have hard veto power over any purchase decision.

## Code style

- Python 3.11+
- Type hints on every function signature, no exceptions
- Docstrings on every public function (Google style)
- Pydantic v2 for all data models — no plain dicts crossing module boundaries
- `httpx` for HTTP, never `requests`
- `structlog` for logging, never `print` in library code (CLI is fine)
- `tenacity` for retries on external calls
- Tests use synthetic fixtures from `data/fixtures/` — never live API calls

## Layout discipline

- Domain logic lives in `src/baby_arb/<domain>/` (pricing, compliance, sourcing, demand)
- Models in `src/baby_arb/models/` — shared across domains
- HTTP clients in `<domain>/clients.py`
- Pure logic in `<domain>/<topic>.py` — no I/O
- CLI commands in `src/baby_arb/cli.py`, thin wrappers calling domain modules

## Hard rules — never violate

1. Never hardcode the 50% margin floor in multiple places. It lives in
   `src/baby_arb/pricing/rules.py` as `MARGIN_FLOOR_PCT` and is the only
   source of truth.
2. Never bypass `compliance.gate(item)` before any buy-decision code path.
3. Never write code that auto-purchases above `MAX_AUTO_BUY_USD` without
   the approval-gate function in the call path.
4. Never hardcode KE customs rates. They live in
   `src/baby_arb/pricing/ke_customs.py` and are env-overridable.
5. Never store credentials in code. `.env` only, loaded via
   `src/baby_arb/config.py`.
6. Never use `pickle` for any data that crosses a process boundary or
   touches disk for >1 hour. JSON via pydantic.
7. Never invent KE retail prices in test fixtures. Use real observed
   data or mark `source: synthetic` explicitly.

## Commit format

`<type>(<scope>): <description>`

Types: `feat fix docs test refactor perf chore ci data eval sourcing pricing`

Examples:
```
pricing(landed-cost): add IDF fee to CIF calculation
sourcing(ebay): retry on 503 with exponential backoff
compliance(recall): add CPSC cache TTL of 24h
test(pricing): add fixtures for 12 stroller listings
```

Always branch `task/<slug>` and open a PR. Never push to main.

## Path-specific guidance

- Editing `src/baby_arb/pricing/`: read `docs/landed_cost_model.md` first.
- Editing `src/baby_arb/compliance/`: read `docs/compliance_rules.md` first.
- Editing scrapers: respect `robots.txt`, rate limit, never store PII.

## When in doubt

Ask. Open a draft PR with a question in the description rather than
guessing on a hard constraint.
