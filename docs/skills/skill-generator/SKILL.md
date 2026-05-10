<!-- Skill version: 0.1 | Last improved: 2026-05-10 | Uses: 0 -->

# Skill Generator

Create new SKILL.md files for new roles or task patterns observed in
operation.

## When to use
- A task type has appeared 2+ times and has no existing skill
- Watson says "create a skill for this"
- A new operational role is needed (FX Hedge Manager, Returns Triager,
  Buyer Trust Scorer, etc.)

## Instructions
1. Read the task pattern from recent conversation history and from
   `docs/progress/` notes.
2. Identify: what triggers this skill, what it does, what it outputs,
   what constraints apply.
3. Write a SKILL.md following the framework format:
   - Header (one-line description)
   - When to use (trigger conditions)
   - Instructions (numbered, specific, no ambiguity)
   - Constraints (non-negotiable rules)
   - Output format (exact structure)
   - Commit format (type and scope for this role's outputs)
   - Self-improvement signals (failure modes that indicate update needed)
4. Write the skill to:
   - Live: `~/.hermes/skills/<name>/SKILL.md`
   - Repo: `docs/skills/<name>/SKILL.md`
5. Add the role to AGENTS.md and SOUL.md role tables in the same PR.
6. Announce the new skill on Telegram with: "New skill <name> live.
   Run 2-3 tasks before Curator review."
7. Tag the skill version 0.1 in the header comment.

## Constraints
- Never duplicate an existing skill — extend or refine instead.
- Never grant a new skill veto power without explicit human approval
  in the PR.
- Never write a skill that bypasses the 50% margin floor.
- Never write a skill that bypasses Compliance Checker.

## Output format
Complete SKILL.md file in the format above.

## Commit format
`chore(skills): add <skill-name> skill`

## Self-improvement signals
- If newly-generated skills get heavily revised by the Curator within
  2 weeks: the templates are too loose. Tighten step 3 with more
  required content checks.
- If a skill is created and never used: prune.
