---
applyTo: "tests/**"
---

# Test instructions

## Discipline

- Tests use synthetic fixtures from `data/fixtures/` only.
- HTTP calls mocked with `respx`. Never hit live APIs in tests.
- Time-dependent tests use `freezegun` or explicit datetime injection.
- Tests in `tests/integration/` are marked `@pytest.mark.integration`
  and excluded by default. They require credentials and are run
  manually before releases.
- One test per spec edge case. Test names describe behaviour,
  not implementation: `test_landed_cost_handles_missing_weight`,
  not `test_landed_cost_function_branch_3`.

## Fixtures

- `data/fixtures/landed_cost_cases.json` — 20+ canonical cases for
  pricing regression
- `data/fixtures/cpsc_recalls_sample.json` — sampled CPSC recalls for
  compliance tests
- `data/fixtures/kebs_restricted.json` — KEBS restricted items
- `data/fixtures/ebay_listings/` — captured eBay listing samples
- `data/fixtures/ke_pricing/` — observed KE retail/used prices

## Coverage targets

- Pricing module: 95%+
- Compliance module: 95%+
- Sourcing module: 80%+ (HTTP-heavy, harder to fully cover)
- Models: 100%
- CLI: smoke tests only

## Commit type

```
test(pricing): add 8 stroller fixtures with expected margins
test(compliance): cover car seat DOM edge cases at exactly 6 years
```
