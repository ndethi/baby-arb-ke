---
applyTo: "src/baby_arb/compliance/**"
---

# Compliance module instructions

This module has veto power over every buy decision. Read
`docs/compliance_rules.md` and
`docs/skills/compliance-checker/SKILL.md` before any change.

## Invariants (never violate)

1. `compliance.gate(item) -> Verdict` is the single entry point.
   Every code path that can lead to a buy MUST call it.
2. A `Verdict` is one of: `PASS`, `BLOCK`, `REVIEW`. There are no
   other states. `BLOCK` is a hard veto — no override anywhere.
3. The CPSC recall cache has a max TTL of 24 hours. Stale cache =
   force refresh, fail closed if refresh fails.
4. Car seat date-of-manufacture ceiling is 6 years. This is in
   `compliance/rules.py` as `CARSEAT_DOM_CEILING_YEARS`.
5. Brand authenticity check applies to: NUNA, UPPAbaby, Stokke,
   BabyBjörn, Doona, Cybex. These have known counterfeit issues.
6. KEBS-restricted items list is a static file at
   `data/fixtures/kebs_restricted.json` — update it via PR, never
   at runtime.

## Change discipline

- Any change that loosens a `BLOCK` decision requires explicit
  human approval in the PR description.
- Adding a new check is fine — defaults to fail-closed.
- Removing a check requires a PR comment from Watson explicitly
  approving the removal.

## Commit type

Use `compliance` if it's a non-code rule change, otherwise standard:
```
fix(compliance): handle CPSC API timeout with cache fallback
data(compliance): refresh KEBS restricted list 2026-05
```
