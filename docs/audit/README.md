# Audit trail

Two records per branch, both committed with the branch and reviewed in its PR.

| Folder | File | Written by | Answers |
|---|---|---|---|
| `prompts/` | `<branch-slug>.md` | the agent (or Watson), each working session | Why did this code change? What was asked, what was decided? |
| `gates/` | `<branch-slug>.md` | `scripts/pre_push.sh`, every run | Was what we pushed linted, tested and security-swept? |

`<branch-slug>` is the branch name with `/` replaced by `-`
(`task/repo-cleanup` → `task-repo-cleanup.md`).

## Prompt log entry

```markdown
## 2026-09-27 · Claude Code (claude-opus-5-5)
**Prompt** (verbatim; redact secrets and third-party personal data as [REDACTED]):
> ...
**Decisions:** assumptions, rejected options and why
**Outcome:** commits, what was left undone
```

Never paste tokens, `.env` values, card numbers, or buyer/seller personal data.
The gate's secret scan covers these files too.

## Gate entry

Appended automatically; one heading per run:

```markdown
## 2026-09-27T12:40Z · a1b2c3d · PASS
- base: origin/main (4672247)
- runner: ndethi

| check | result | detail |
|---|---|---|
| branch | PASS | task/repo-cleanup |
| ...
```

The SHA is the latest commit that touched anything outside `docs/audit/gates/`, so
committing the record itself does not invalidate it. The pre-push hook looks
for a `PASS` heading with that SHA before allowing the push.
