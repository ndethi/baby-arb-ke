---
name: dev-lifecycle
description: The baby-arb-ke workflow for any code or docs change - branch, prompt log, implement with tests, self-review, commit, pre-push gate, PR. Use for every change that should end in a commit.
---
<!-- Skill version: 0.1 | Last improved: 2026-09-27 | Uses: 0 -->

# Dev lifecycle

Read `SOUL.md` and `AGENTS.md` first. Their hard constraints override anything here.

## When to use
Any task that changes files in this repo.

## Instructions
1. **Orient.** `git status`, `git log --oneline origin/main..HEAD`. Know which
   changes are yours. Never commit changes you did not make or cannot explain.
2. **Branch.** `git switch -c task/<slug> origin/main` (lower-case, hyphens).
   One task per branch. Never commit to `main`.
   Hermes cron jobs run from this working copy: do not switch branches or
   move files they call (`~/.hermes/cron/jobs.json`) without checking first.
3. **Prompt log.** Create or append `docs/audit/prompts/<branch-slug>.md`
   (branch name with `/` replaced by `-`). One entry per working session:
   ```markdown
   ## 2026-09-27 · <agent> (<model id>)
   **Prompt** (verbatim; redact secrets and third-party personal data as [REDACTED]):
   > ...
   **Decisions:** assumptions made, options rejected, and why
   **Outcome:** commits made, what was left undone
   ```
   The log records why the code changed. Never paste tokens, `.env` values,
   card numbers or buyer/seller personal data.
4. **Implement.** Docstrings and type hints on every function. Tests with the
   change (synthetic fixtures only; mock HTTP with respx). A bug fix needs a
   test that fails without it. Never fabricate market data: if a source is
   unavailable, return UNKNOWN with a reason, never demo values.
5. **Self-review.** Read `git diff` as a reviewer: correctness, edge cases,
   unintended behaviour change, dead code, anything touching pricing or
   compliance vetoes.
6. **Commit.** Stage by explicit path, never `git add -A`. One logical change
   per commit, `<type>(<scope>): <description>` with types from `.cz.toml`,
   lower-case subject, header at most 100 chars. Body explains why.
7. **Gate.** Run the `pre-push` skill and commit its record.
8. **PR.** Push only when asked. Open a PR to `main` using
   `.github/PULL_REQUEST_TEMPLATE.md`. Paste the gate table and link the
   prompt log. Watson merges; agents never merge their own PRs.
9. **Report.** What shipped, gate result, and anything found but not fixed.

## Commit discipline
Types: `feat fix docs test refactor perf chore ci data eval sourcing pricing`.
