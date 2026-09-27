# Prompt log · task/repo-cleanup

## 2026-09-27 · Claude Code (claude-opus-5-5)

**Prompt** (verbatim):
> Lets read this read me and return understanding here before we set next steps

> clean up the repo , then consider how we make this useful by live automated scraping , we want to also do relevant skills to clean up repo, make sure we do best practice in terms of code, including tags, branches, prompt logs, security sweeps etc - latter should be - lets think if one skill or several, that we can call befoer push and log it as such

**Decisions:**
- Branched `task/repo-cleanup` from `task/weekly-brief-2026-06-22` (current HEAD) because nothing
  has been merged to `main` yet; the PR therefore also carries the three earlier unmerged commits.
- Cleanup is reversible: 44 scratch/backup files moved to gitignored `.archive/2026-09-27/`
  instead of deleted (deletion was blocked as irreversible). Root debug scripts, `*.bak`,
  `*.backup*`, `*.orig`, `*.broken`, `*.telegram*` copies, `exit_code.txt`, `scripts/scrape_reddit_debug.py`.
- Did not move any script referenced by `~/.hermes/cron/jobs.json`; five cron jobs run from
  this working copy. Only `update_demand_signals.py` (unreferenced) moved into `scripts/`.
- Committed the untracked prototype collectors and ops scripts as-is (plus ruff safe fixes)
  so the code Hermes runs is under version control. They still return demo data; fixing that
  is Phase 0 of `docs/live_scraping_plan.md`, not this branch.
- `poetry.lock` was gitignored; unpinned resolution pulled click 8.4 which breaks typer 0.12
  (6 CLI tests failing). Bumped typer to ^0.16 and committed the lock file.
- Skills: one gate (`pre-push`) called before every push, which writes the record, plus
  `dev-lifecycle` (branches, prompt log, commits) and `release` (tags). One gate rather than
  several because the requirement is a single call before push with one logged result;
  checks stay modular inside `scripts/pre_push.sh`.
- Hooks via committed `.githooks/` + `core.hooksPath` rather than pre-commit (the README
  referenced a pre-commit config that did not exist; plain hooks need no network).
- Records live in `docs/audit/`, not `docs/logs/`, because `.gitignore` ignores `logs/`.
- Moved the demand report debug copy from `/tmp` to `data/cache/` (bandit B108). Checked
  Hermes cron jobs and the daily-demand-alert skill: neither reads the `/tmp` file.
- Left alone: 26 strict-mypy errors in `src/` (CI runs mypy and will fail), the `compliance`
  commit type used in AGENTS.md examples but missing from `.cz.toml`, stale `origin/master`,
  and the non-conforming `feature/on-demand-breast-pump-check` branch name. Listed for Watson.

**Outcome:** see commits on this branch; gate record in `docs/audit/gates/task-repo-cleanup.md`.

### Gate follow-up (same session)
- First gate run FAILED on pip-audit (7 advisories in anyio, pydantic-settings, soupsieve,
  pytest); fixed in `fix(deps): upgrade packages with known cves`. The pytest 9 upgrade silently
  broke collection with pytest-asyncio 0.23 ("no tests ran"), caught before commit; bumped to ^1.2.
- The first run also showed the gated SHA skipped prompt-log commits; narrowed the exclusion to
  `docs/audit/gates/` only.

## 2026-09-27 · Claude Code (claude-opus-5-5)

**Prompt** (verbatim):
> 1. demo-fed crons should stop

**Decisions:**
- Paused (not removed) the six jobs whose output derives from demo values: demand-update and
  multi-source (demo collectors), daily-alert, weekly-brief and weekly-demand-gen (read the
  demand_scout cache those collectors write), aggregator-top5 (demo-tuned multipliers, trackers
  stale since 2026-06-01). Backup of jobs.json taken before the change.
- Jobs live in the Hermes `default` profile while the sticky profile is `faber`, so plain
  `hermes cron pause` reported "not found"; used `hermes --profile default`.
- Left smart-baby-tech-demand-gen running: it has no demo values, but its scores are HTML word
  counts. Flagged for Watson rather than paused, since the instruction was "demo-fed".

**Outcome:** jobs paused and verified in `~/.hermes/cron/jobs.json`; plan doc updated.

## 2026-09-27 · Claude Code (claude-opus-5-5)

**Prompt** (verbatim):
> i dont have ebay dev keys, how do i go around this
> jiji scrape pages directly
> lets keep those other scrapters
> pr yes lets push that pr and open it

**Decisions:**
- Recorded in `docs/live_scraping_plan.md`: register eBay developer app (with account-deletion
  exemption); build Phase 1 against fixtures/sandbox meanwhile; Jiji via direct HTML; keep the
  Reddit/BabyCenter/Mumsnet and Mercari/OfferUp/FB scrapers and migrate them in Phase 3.
- Noted eBay robots.txt disallows `/sch/i.html?_nkw=`, which the kept scrapers use.

**Outcome:** plan updated; branch pushed and PR opened for Watson's review.
