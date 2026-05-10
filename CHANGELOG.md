# Changelog

All notable changes to baby-arb-ke will be documented here.
Format: [Conventional Commits](https://www.conventionalcommits.org/).

## [0.1.0] — 2026-05-10

### Initial MVP scaffold

#### feat
- Pricing engine: deterministic landed-cost calculator with US sales tax,
  warehouse handling, dim-weight-aware international shipping, KE customs
  (duty + VAT + IDF + RDL), insurance, and last-mile fees
- Pricing verdict: BUY/SKIP/ABSTAIN/REVIEW with margin floor enforcement
- Compliance gate: 5-layer check (safety blocks, car seat DOM, authenticity,
  KEBS, CPSC) with cheapest-first short-circuit and fail-closed defaults
- Demand aggregator: composite score from Jiji, retail, FB, social signals
  with confidence assessment based on missing-data weight
- CLI: typer-based with `price`, `compliance`, `demand`, `brief`, `health`,
  `version` subcommands

#### docs
- SOUL.md, AGENTS.md, README.md
- architecture.md, landed_cost_model.md, compliance_rules.md,
  demand_signals.md, operating_runbook.md, HERMES_HANDOFF.md
- 10 SKILL.md files for the agent team
- Path-specific instructions for Copilot in pricing, compliance, tests, docs
- 3 Copilot cloud agent profiles

#### test
- 49 tests passing across pricing, compliance, demand, and CLI smoke
- Synthetic fixtures only — no live API calls
- conftest.py with isolated cache dirs per test

#### ci
- commitlint workflow blocks bad commits on PR
- changelog workflow auto-generates CHANGELOG on merge to main
- test workflow runs ruff + mypy + pytest on Python 3.11 + 3.12

#### chore
- Poetry-based dependency management
- Commitizen + Conventional Commits enforcement
- ruff + mypy linting
- PR template with margin/compliance impact section
