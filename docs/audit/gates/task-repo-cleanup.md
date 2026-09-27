# Gate log · task/repo-cleanup

One entry per pre-push gate run. Written by scripts/pre_push.sh.

## 2026-09-27T12:54Z · 396c408 · FAIL

- base: origin/main (4672247)
- runner: ndethi

| check | result | detail |
|---|---|---|
| branch | PASS | task/repo-cleanup |
| clean-tree | PASS |  |
| commits | PASS | 13 commits |
| hygiene | PASS |  |
| ruff | PASS | 17 files |
| ruff-scripts | WARN | lint debt in changed ops scripts (advisory) |
| pytest | PASS |  |
| bandit | PASS | medium+ severity |
| secrets | PASS | regex fallback (gitleaks not installed) |
| pip-audit | FAIL | vulnerable deps, or audit could not run (set SKIP_AUDIT=<reason> only if offline) |
| prompt-log | PASS | docs/audit/prompts/task-repo-cleanup.md |

## 2026-09-27T12:58Z · 07a7e86 · PASS

- base: origin/main (4672247)
- runner: ndethi

| check | result | detail |
|---|---|---|
| branch | PASS | task/repo-cleanup |
| clean-tree | PASS |  |
| commits | PASS | 16 commits |
| hygiene | PASS |  |
| ruff | PASS | 17 files |
| ruff-scripts | WARN | lint debt in changed ops scripts (advisory) |
| pytest | PASS |  |
| bandit | PASS | medium+ severity |
| secrets | PASS | regex fallback (gitleaks not installed) |
| pip-audit | PASS |  |
| prompt-log | PASS | docs/audit/prompts/task-repo-cleanup.md |

## 2026-09-27T13:14Z · 0430fbc · PASS

- base: origin/main (4672247)
- runner: ndethi

| check | result | detail |
|---|---|---|
| branch | PASS | task/repo-cleanup |
| clean-tree | PASS |  |
| commits | PASS | 18 commits |
| hygiene | PASS |  |
| ruff | PASS | 17 files |
| ruff-scripts | WARN | lint debt in changed ops scripts (advisory) |
| pytest | PASS |  |
| bandit | PASS | medium+ severity |
| secrets | PASS | regex fallback (gitleaks not installed) |
| pip-audit | PASS |  |
| prompt-log | PASS | docs/audit/prompts/task-repo-cleanup.md |
