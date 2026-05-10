---
applyTo: "docs/**"
---

# Documentation instructions

## Discipline

- Match register to deliverable:
  - `docs/architecture.md` etc — technical, concise
  - `docs/skills/*/SKILL.md` — instruction format, no prose
  - `docs/operating_runbook.md` — operator-facing, terse, action-oriented
- Language rules:
  - No AI-marker phrases ("it is worth noting", "importantly", "delve")
  - No em dashes
  - No nominalisation where a verb works
  - Bullet points only for lists of comparable items
- Never imply the system has capabilities it does not yet have.
  MVP scope is explicit and time-bound.
- Never cite unresolved publications or made-up sources.

## When updating

- Skills: update both `~/.hermes/skills/<name>/SKILL.md` (the live
  copy) and `docs/skills/<name>/SKILL.md` (the repo snapshot).
- Architecture changes: update `docs/architecture.md` AND
  `AGENTS.md` repo structure section in the same PR.
- New constraints: update `SOUL.md` AND `AGENTS.md` hard constraints.

## Commit type

```
docs(architecture): document the demand signal pipeline
docs(skills): update pricing-engineer with FX hedge rules
```
