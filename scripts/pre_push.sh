#!/usr/bin/env bash
# Pre-push gate for baby-arb-ke. Run before every push; see docs/skills/pre-push/SKILL.md.
#
#   scripts/pre_push.sh [base-ref]      default base: origin/main (falls back to main)
#   SKIP_AUDIT="<reason>" scripts/pre_push.sh   skip pip-audit (e.g. offline); reason is logged
#
# Checks: branch name, clean tree, commit messages, repo hygiene, ruff, pytest,
# bandit, secret scan, pip-audit, prompt log. Appends a run record to
# docs/audit/gates/<branch-slug>.md, which you commit before pushing.
# The pre-push git hook (scripts/verify_gate_record.sh) refuses a push without a PASS record.
set -uo pipefail
unset VIRTUAL_ENV # always use this project's Poetry env, not whatever shell venv is active

cd "$(git rev-parse --show-toplevel)"
BASE="${1:-}"
if [ -z "$BASE" ]; then
  if git rev-parse -q --verify origin/main >/dev/null; then BASE=origin/main; else BASE=main; fi
fi
BRANCH="$(git branch --show-current)"
SLUG="${BRANCH//\//-}"
# Last commit touching anything outside docs/audit/ = the code being gated.
SHA="$(git log -1 --format=%h -- . ':(exclude)docs/audit')"
RUN="poetry run"
mkdir -p .gate docs/audit/gates
OUT=".gate/$(date -u +%Y%m%dT%H%M%SZ)-${SLUG}.txt"

record() { echo "[$2] $1${3:+ - $3}"; }

echo "[INFO] gate: branch=$BRANCH sha=$SHA base=$BASE (full output: $OUT)"
{
  # 1. Branch
  if [[ "$BRANCH" =~ ^task/[a-z0-9][a-z0-9.-]*$ ]]; then
    record branch PASS "$BRANCH"
  else
    record branch FAIL "'$BRANCH' is not task/<slug> (never push main)"
  fi

  # 2. Clean tree: the gate must test exactly what is committed.
  DIRTY="$(git status --porcelain -- . ':(exclude)docs/audit' | wc -l | tr -d ' ')"
  if [ "$DIRTY" = "0" ]; then record clean-tree PASS ""; else record clean-tree FAIL "$DIRTY uncommitted/untracked paths"; fi

  # 3. Commit messages
  if python3 scripts/check_commit_msg.py --range "$BASE..HEAD"; then
    record commits PASS "$(git rev-list --count --no-merges "$BASE..HEAD") commits"
  else
    record commits FAIL "see messages above"
  fi

  # 4. Hygiene
  H=""
  BAD="$(git ls-files | grep -E '\.(bak|orig|broken)$|\.backup' || true)"; [ -n "$BAD" ] && H="$H backup-files:$(echo "$BAD" | wc -l | tr -d ' ')"
  BAD="$(git ls-files | grep -E '^[^/]+\.py$' || true)"; [ -n "$BAD" ] && H="$H root-py:$(echo "$BAD" | tr '\n' ' ')"
  BAD="$(git ls-files | grep -E '(^|/)\.env$' || true)"; [ -n "$BAD" ] && H="$H tracked-.env"
  for f in $(git diff --name-only --diff-filter=AM "$BASE...HEAD"); do
    [ -f "$f" ] && [ "$(wc -c <"$f")" -gt 1048576 ] && H="$H large:$f"
  done
  if [ -z "$H" ]; then record hygiene PASS ""; else record hygiene FAIL "$H"; fi

  # 5. Lint: blocking for src/ and tests/, advisory for ops scripts.
  CHANGED="$( { git diff --name-only --diff-filter=d "$BASE...HEAD"; git diff --name-only --diff-filter=d HEAD; } | sort -u | grep '\.py$' || true)"
  CORE="$(echo "$CHANGED" | grep -E '^(src|tests)/' || true)"
  OPS="$(echo "$CHANGED" | grep -Ev '^(src|tests)/' | grep . || true)"
  if [ -z "$CORE" ]; then
    record ruff PASS "no changed src/tests files"
  elif $RUN ruff check $CORE; then
    record ruff PASS "$(echo "$CORE" | wc -l | tr -d ' ') files"
  else
    record ruff FAIL "src/tests lint errors"
  fi
  if [ -n "$OPS" ] && ! $RUN ruff check -q $OPS >/dev/null; then
    record ruff-scripts WARN "lint debt in changed ops scripts (advisory)"
  fi

  # 6. Tests
  if $RUN pytest -q -p no:cacheprovider; then record pytest PASS ""; else record pytest FAIL ""; fi

  # 7. Security: bandit (medium+), secrets, dependency CVEs
  if $RUN bandit -q -ll -r src scripts devops; then record bandit PASS "medium+ severity"; else record bandit FAIL "medium+ findings"; fi

  if command -v gitleaks >/dev/null; then
    if gitleaks git --no-banner --redact --log-opts="$BASE..HEAD" . 2>/dev/null \
      || gitleaks detect --no-banner --redact --log-opts="$BASE..HEAD" 2>/dev/null; then
      record secrets PASS "gitleaks $(gitleaks version)"
    else
      record secrets FAIL "gitleaks found candidates (output redacted)"
    fi
  else
    if git log -p "$BASE..HEAD" | grep -E '^\+' | grep -Eiq '(api[_-]?key|secret|token|passwd|password)["'"'"']?[[:space:]]*[=:][[:space:]]*["'"'"'][A-Za-z0-9_/+=-]{16,}|-----BEGIN [A-Z ]*PRIVATE KEY|AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{30,}|sk-[A-Za-z0-9]{20,}|xox[abpr]-[A-Za-z0-9-]{10,}|[0-9]{8,10}:AA[A-Za-z0-9_-]{30,}'; then
      record secrets FAIL "regex scan hit (install gitleaks for detail)"
    else
      record secrets PASS "regex fallback (gitleaks not installed)"
    fi
  fi

  if [ -n "${SKIP_AUDIT:-}" ]; then
    record pip-audit SKIP "$SKIP_AUDIT"
  elif $RUN pip-audit --skip-editable --progress-spinner off; then
    record pip-audit PASS ""
  else
    record pip-audit FAIL "vulnerable deps, or audit could not run (set SKIP_AUDIT=<reason> only if offline)"
  fi

  # 8. Prompt log for this branch
  PLOG="docs/audit/prompts/${SLUG}.md"
  if [ -f "$PLOG" ] && git diff --name-only "$BASE...HEAD" | grep -qx "$PLOG"; then
    record prompt-log PASS "$PLOG"
  else
    record prompt-log FAIL "missing or not updated on this branch: $PLOG"
  fi
} 2>&1 | tee "$OUT.raw"
# The block above ran in a pipeline subshell; recover the results from its output.
STATUS=PASS
grep -Eq '^\[FAIL\] ' "$OUT.raw" && STATUS=FAIL
mv "$OUT.raw" "$OUT"

GATE_LOG="docs/audit/gates/${SLUG}.md"
[ -f "$GATE_LOG" ] || printf '# Gate log · %s\n\nOne entry per pre-push gate run. Written by scripts/pre_push.sh.\n' "$BRANCH" >"$GATE_LOG"
{
  printf '\n## %s · %s · %s\n\n' "$(date -u +%Y-%m-%dT%H:%MZ)" "$SHA" "$STATUS"
  printf -- '- base: %s (%s)\n- runner: %s\n\n| check | result | detail |\n|---|---|---|\n' \
    "$BASE" "$(git rev-parse --short "$BASE")" "$(git config user.name)"
  grep -E '^\[(PASS|FAIL|WARN|SKIP)\] ' "$OUT" | sed -E 's/^\[([A-Z]+)\] ([^ ]+)( - (.*))?$/| \2 | \1 | \4 |/'
} >>"$GATE_LOG"

echo
if [ "$STATUS" = PASS ]; then
  echo "[INFO] gate PASSED for $SHA. Record it, then push:"
  echo "  git add $GATE_LOG && git commit -m \"chore(audit): record pre-push gate for $SHA\""
  exit 0
fi
echo "[ERROR] gate FAILED for $SHA (entry written to $GATE_LOG). Fix and re-run; do not push."
exit 1
