---
name: pre-push
description: Run the baby-arb-ke pre-push gate (branch, commit format, repo hygiene, ruff, pytest, bandit, secret scan, pip-audit, prompt log) and commit its log entry. Use before every git push, and whenever asked to lint, test, or security-sweep the repo.
---
<!-- Skill version: 0.1 | Last improved: 2026-09-27 | Uses: 0 -->

# Pre-push gate

One gate, run before every push. It checks everything that must hold for a
branch to leave this machine, and it leaves a committed record that it ran.

## When to use
- Before any `git push`, by any agent or by Watson.
- "Lint / test / security-check / sweep the repo".
- After rebasing or amending a branch that was already gated.

## Instructions
1. Commit your work first. The gate refuses a dirty tree: it must test
   exactly what will be pushed. Make sure this branch's prompt log
   (`docs/audit/prompts/<branch-slug>.md`) is updated and committed (see the
   `dev-lifecycle` skill).
2. Run from the repo root:
   ```bash
   scripts/pre_push.sh                  # base: origin/main
   scripts/pre_push.sh <base-ref>       # stacked branch
   SKIP_AUDIT="offline" scripts/pre_push.sh   # only when pip-audit cannot reach the network
   ```
3. If it fails: fix the cause, commit, re-run. Every run (pass or fail) is
   appended to `docs/audit/gates/<branch-slug>.md`.
4. If it passes, commit the record exactly as the script prints:
   `chore(audit): record pre-push gate for <sha>`
5. Push. The git `pre-push` hook (`.githooks/pre-push` →
   `scripts/verify_gate_record.sh`) checks for a committed PASS entry matching
   the latest non-audit commit, and refuses pushes to `main`/`master`.
   Hooks are enabled once per clone with `git config core.hooksPath .githooks`.

## What it checks
| Check | Blocks | Notes |
|---|---|---|
| branch | yes | `task/<slug>`; never `main` |
| clean-tree | yes | nothing uncommitted outside `docs/audit/` |
| commits | yes | every commit since base matches `.cz.toml` `schema_pattern` |
| hygiene | yes | no tracked backups (`*.bak`, `*.backup*`, `*.orig`), no root-level `.py`, no tracked `.env`, no added file over 1 MB |
| ruff | yes | changed files in `src/` and `tests/` |
| ruff-scripts | no | changed ops scripts; advisory while legacy debt remains |
| pytest | yes | full suite |
| bandit | yes | medium+ severity over `src scripts devops` |
| secrets | yes | gitleaks if installed, else regex over added lines |
| pip-audit | yes | known CVEs in installed deps |
| prompt-log | yes | branch prompt log exists and changed on this branch |

## Rules
- Never skip, weaken or silence a check to get green. No `git push --no-verify`.
- `# nosec` / `# noqa` only for a genuine false positive, with the reason inline.
- `SKIP_AUDIT` is for no network only. Its reason goes into the log; say so in the PR.
- Report the actual gate output. A check that could not run did not pass.
- Fix findings in files you touched. List pre-existing issues elsewhere in the PR
  instead of fixing them in the same commit.

## Commit discipline
`chore(audit): record pre-push gate for <sha>` for the record commit only.
