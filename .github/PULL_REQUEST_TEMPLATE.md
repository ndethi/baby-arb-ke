## What this does
<!-- One paragraph. What changed and why. -->

## Type of change
<!-- Delete inapplicable lines -->
- feat: new feature or capability
- fix: bug fix
- docs: documentation only
- test: test additions or changes
- sourcing: marketplace client / scraper changes
- pricing: landed-cost / margin rule changes
- data: dataset or fixture changes
- eval: margin reconciliation / metric changes
- chore: config or tooling

## Tasks completed
<!-- Reference the GitHub Issue checklist items this PR closes -->
- Closes task #N.N in issue #[n]

## Files changed
<!-- List key files and one-line description of each change -->
| File | Change |
|------|--------|
|      |        |

## Agent checklist
<!-- Hermes/Copilot: verify these before opening the PR -->
- [ ] Commits follow Conventional Commits format
- [ ] No direct push to main — this is a branch PR
- [ ] All new functions have docstrings + type hints
- [ ] Edge cases from spec are handled
- [ ] Tests exist for all data-transforming functions
- [ ] No hardcoded secrets, paths, or credentials
- [ ] If pricing logic changed: regression tests against fixtures pass
- [ ] If compliance logic changed: never-buy invariants still hold
- [ ] `status: approved` on any buy candidate is NOT set by automation

## Margin / compliance impact
<!-- Required for sourcing/pricing/compliance PRs -->
- [ ] No change to margin floor (50%)
- [ ] No change to recall veto behaviour
- [ ] No change to car-seat DOM ceiling (6 years)
- [ ] No change to auto-buy threshold ($200) without explicit approval

## Review notes
<!-- Anything Watson should check specifically -->
