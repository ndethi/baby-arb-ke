# Gate log · task/mkt-phase0-foundations

One entry per pre-push gate run. Written by scripts/pre_push.sh.

## 2026-11-21T07:36Z · 09f174b · FAIL

- base: origin/task/phase0-no-demo-data (3fb8d93)
- runner: ndethi

| check | result | detail |
|---|---|---|
| branch | PASS | task/mkt-phase0-foundations |
| clean-tree | PASS |  |
| commits | PASS | 9 commits |
| hygiene | PASS |  |
| ruff | PASS | 32 files |
| ruff-scripts | WARN | lint debt in changed ops scripts (advisory) |
| pytest | PASS |  |
| bandit | PASS | medium+ severity |
| secrets | PASS | regex fallback (gitleaks not installed) |
| pip-audit | FAIL | vulnerable deps, or audit could not run (set SKIP_AUDIT=<reason> only if offline) |
| prompt-log | PASS | docs/audit/prompts/task-mkt-phase0-foundations.md |

## 2026-11-21T07:39Z · 1c96073 · PASS

- base: origin/task/phase0-no-demo-data (3fb8d93)
- runner: ndethi

| check | result | detail |
|---|---|---|
| branch | PASS | task/mkt-phase0-foundations |
| clean-tree | PASS |  |
| commits | PASS | 10 commits |
| hygiene | PASS |  |
| ruff | PASS | 32 files |
| ruff-scripts | WARN | lint debt in changed ops scripts (advisory) |
| pytest | PASS |  |
| bandit | PASS | medium+ severity |
| secrets | PASS | regex fallback (gitleaks not installed) |
| pip-audit | PASS |  |
| prompt-log | PASS | docs/audit/prompts/task-mkt-phase0-foundations.md |
