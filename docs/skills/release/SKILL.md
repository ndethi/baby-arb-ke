---
name: release
description: Cut a baby-arb-ke release - commitizen version bump, CHANGELOG, annotated vX.Y.Z tag on main. Use only when Watson asks to release or tag, after PRs are merged.
---
<!-- Skill version: 0.1 | Last improved: 2026-09-27 | Uses: 0 -->

# Release

Tags mark versions Watson has accepted. They are cut from `main` only, after merge.

## When to use
- Watson says "release", "tag", "cut a version", or "bump".
- Never as part of a feature branch, never automatically.

## Instructions
The bump goes through a PR like everything else; only the tag is pushed directly.

1. `git fetch && git switch -c task/release origin/main`. Confirm CI is green on
   `main` (`gh run list --branch main -L 3`).
2. Preview: `poetry run cz bump --dry-run`. It derives the increment from commit
   types since the last tag (`feat` = minor, `fix`/`perf` = patch, `!` = major;
   pre-1.0 stays `0.x`). Show Watson the version and changelog preview and wait
   for a go-ahead.
3. `poetry run cz bump --files-only --changelog --yes`. This updates
   `pyproject.toml`, `src/baby_arb/__init__.py` and `CHANGELOG.md` without
   committing or tagging. Rename the branch to `task/release-vB`, commit
   `bump: version A → B`, add a prompt-log entry, run the `pre-push` skill,
   push, open the PR.
4. After Watson merges: `git switch main && git pull --ff-only`, then tag the
   merge commit: `git tag -a vB -m "vB: <one-line summary>"` and
   `git push origin vB`. The pre-push hook allows tag-only pushes.
5. Optional: `gh release create vB --notes "<CHANGELOG section>"`.

## Rules
- Never move or delete a pushed tag. Fix forward with a new patch version.
- Tags are `v<semver>` (`.cz.toml` `tag_format`). No other tag names on `main`.
- Shadow-mode milestones (e.g. first real purchase) are a minor bump with the
  milestone in the tag annotation.

## Commit discipline
Only commitizen writes `bump:` commits.
