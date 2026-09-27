#!/usr/bin/env bash
# git pre-push hook body (wired via .githooks/pre-push). Reads the refs being pushed on stdin:
#   <local ref> <local sha> <remote ref> <remote sha>
# - pushes to main/master are refused (use a PR);
# - tag pushes are allowed (release skill);
# - branch pushes need a committed PASS entry in docs/audit/gates/<branch-slug>.md for the
#   latest commit on that branch that touched anything outside docs/audit/gates/.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

FAIL=0
while read -r LOCAL_REF LOCAL_SHA REMOTE_REF _; do
  case "$REMOTE_REF" in
    refs/tags/*) continue ;;
    refs/heads/main | refs/heads/master)
      echo "[ERROR] refusing push to ${REMOTE_REF#refs/heads/}; open a PR from a task/<slug> branch"
      FAIL=1; continue ;;
  esac
  [ "$LOCAL_SHA" = "0000000000000000000000000000000000000000" ] && continue # branch deletion
  BRANCH="${LOCAL_REF#refs/heads/}"
  CODE_SHA="$(git log -1 --format=%h "$LOCAL_SHA" -- . ':(exclude)docs/audit/gates')"
  GATE_LOG="docs/audit/gates/${BRANCH//\//-}.md"
  if git show "$LOCAL_SHA:$GATE_LOG" 2>/dev/null | grep -Eq "^## .* · ${CODE_SHA} · PASS$"; then
    echo "[INFO] $BRANCH: gate record found for $CODE_SHA"
  else
    echo "[ERROR] $BRANCH: no committed PASS gate record for $CODE_SHA in $GATE_LOG"
    echo "        run scripts/pre_push.sh, commit the log entry it prints, then push"
    FAIL=1
  fi
done
exit "$FAIL"
