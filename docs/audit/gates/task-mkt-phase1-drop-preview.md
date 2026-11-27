# Gate log · task/mkt-phase1-drop-preview

One entry per pre-push gate run. Written by scripts/pre_push.sh.

## 2026-11-27T07:00Z · df17412 · FAIL

- base: origin/task/mkt-phase0-foundations (c781e57)
- runner: ndethi

| check | result | detail |
|---|---|---|
| branch | PASS | task/mkt-phase1-drop-preview |
| clean-tree | PASS |  |
| commits | PASS | 8 commits |
| hygiene | PASS |  |
| ruff | PASS | 30 files |
| pytest | PASS |  |
| bandit | PASS | medium+ severity |
| secrets | PASS | regex fallback (gitleaks not installed) |
| pip-audit | FAIL | vulnerable deps, or audit could not run (set SKIP_AUDIT=<reason> only if offline) |
| prompt-log | PASS | docs/audit/prompts/task-mkt-phase1-drop-preview.md |

## 2026-11-27T07:01Z · 3ad1887 · PASS

- base: origin/task/mkt-phase0-foundations (c781e57)
- runner: ndethi

| check | result | detail |
|---|---|---|
| branch | PASS | task/mkt-phase1-drop-preview |
| clean-tree | PASS |  |
| commits | PASS | 9 commits |
| hygiene | PASS |  |
| ruff | PASS | 30 files |
| pytest | PASS |  |
| bandit | PASS | medium+ severity |
| secrets | PASS | regex fallback (gitleaks not installed) |
| pip-audit | PASS |  |
| prompt-log | PASS | docs/audit/prompts/task-mkt-phase1-drop-preview.md |

## 2026-11-27T07:03Z · 5b12a9e · FAIL

- base: origin/task/mkt-phase0-foundations (c781e57)
- runner: ndethi

| check | result | detail |
|---|---|---|
| branch | PASS | task/mkt-phase1-drop-preview |
| clean-tree | FAIL | 2 uncommitted/untracked paths |
| commits | PASS | 11 commits |
| hygiene | PASS |  |
| ruff | PASS | 30 files |
| pytest | PASS |  |
| bandit | PASS | medium+ severity |
| secrets | PASS | regex fallback (gitleaks not installed) |
| pip-audit | PASS |  |
| prompt-log | PASS | docs/audit/prompts/task-mkt-phase1-drop-preview.md |

## 2026-11-27T07:04Z · f055db1 · PASS

- base: origin/task/mkt-phase0-foundations (c781e57)
- runner: ndethi

| check | result | detail |
|---|---|---|
| branch | PASS | task/mkt-phase1-drop-preview |
| clean-tree | PASS |  |
| commits | PASS | 12 commits |
| hygiene | PASS |  |
| ruff | PASS | 30 files |
| pytest | PASS |  |
| bandit | PASS | medium+ severity |
| secrets | PASS | regex fallback (gitleaks not installed) |
| pip-audit | PASS |  |
| prompt-log | PASS | docs/audit/prompts/task-mkt-phase1-drop-preview.md |

## 2026-11-27T07:27Z · ac022dc · PASS

- base: origin/task/mkt-phase0-foundations (c781e57)
- runner: ndethi

| check | result | detail |
|---|---|---|
| branch | PASS | task/mkt-phase1-drop-preview |
| clean-tree | PASS |  |
| commits | PASS | 14 commits |
| hygiene | PASS |  |
| ruff | PASS | 30 files |
| pytest | PASS |  |
| bandit | PASS | medium+ severity |
| secrets | PASS | regex fallback (gitleaks not installed) |
| pip-audit | PASS |  |
| prompt-log | PASS | docs/audit/prompts/task-mkt-phase1-drop-preview.md |

## 2026-11-27T08:16Z · 1ddef9a · PASS

- base: origin/task/mkt-phase0-foundations (c781e57)
- runner: ndethi

| check | result | detail |
|---|---|---|
| branch | PASS | task/mkt-phase1-drop-preview |
| clean-tree | PASS |  |
| commits | PASS | 19 commits |
| hygiene | PASS |  |
| ruff | PASS | 30 files |
| ruff-scripts | WARN | lint debt in changed ops scripts (advisory) |
| pytest | PASS |  |
| bandit | PASS | medium+ severity |
| secrets | PASS | regex fallback (gitleaks not installed) |
| pip-audit | PASS |  |
| prompt-log | PASS | docs/audit/prompts/task-mkt-phase1-drop-preview.md |
