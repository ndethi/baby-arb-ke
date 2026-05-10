---
applyTo: "src/baby_arb/pricing/**"
---

# Pricing module instructions

You are working in the pricing engine. This is the highest-stakes
module in the codebase. Read `docs/landed_cost_model.md` and
`docs/skills/pricing-engineer/SKILL.md` before any change.

## Invariants (never violate)

1. Margin floor lives in ONE place: `src/baby_arb/pricing/rules.py`,
   constant `MARGIN_FLOOR_PCT`. If you find it duplicated anywhere
   else, that is a bug — fix it as part of your change.
2. The landed-cost calculation is pure and deterministic. No LLM
   calls, no randomness, no hidden side effects.
3. Every cost component is a named, typed field on `LandedCost`.
   Never collapse fees into a single "fees" number.
4. KE customs duty, VAT, IDF, and RDL are calculated on CIF
   (Cost + Insurance + Freight). Get the order right.
5. FX rates are sourced via `pricing/fx.py`. Never hardcode rates.
6. If any input is `None` or missing, the function returns
   `LandedCost(confidence=LOW)` — it does NOT raise. The decision
   layer reads confidence and decides whether to abstain.

## Change discipline

- Any change to the formula requires regression tests against the
  fixtures in `tests/fixtures/landed_cost_cases.json`.
- Adding a new fee requires updating `docs/landed_cost_model.md` in
  the same PR.
- Changing the margin floor requires changing `SOUL.md` constraint
  and getting human approval — flag this clearly in the PR.

## Commit type

Use `pricing` for all changes here:
```
pricing(landed-cost): handle missing weight with conservative estimate
pricing(rules): tighten margin floor to 55% for car seats
```
