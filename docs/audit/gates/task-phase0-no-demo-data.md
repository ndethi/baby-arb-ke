# Gate log · task/phase0-no-demo-data

One entry per pre-push gate run. Written by scripts/pre_push.sh.

## 2026-10-20T09:10Z · 9ee0b16 · FAIL

- base: origin/task/repo-cleanup (ab3dc7c)
- runner: ndethi

| check | result | detail |
|---|---|---|
| branch | PASS | task/phase0-no-demo-data |
| clean-tree | PASS |  |
| commits | PASS | 9 commits |
| hygiene | PASS |  |
| ruff | PASS | 15 files |
| ruff-scripts | WARN | lint debt in changed ops scripts (advisory) |
| pytest | PASS |  |
| bandit | PASS | medium+ severity |
| secrets | PASS | regex fallback (gitleaks not installed) |
| pip-audit | FAIL | vulnerable deps, or audit could not run (set SKIP_AUDIT=<reason> only if offline) |
| prompt-log | PASS | docs/audit/prompts/task-phase0-no-demo-data.md |
