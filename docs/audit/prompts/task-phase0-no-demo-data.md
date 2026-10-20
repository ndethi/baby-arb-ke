# Prompt log · task/phase0-no-demo-data

## 2026-10-20 · Claude Code (claude-opus-5-5)

**Prompt** (verbatim):
> open PRs for task/repo-cleanup so I can review them then we can move on to phase 0 cleanup and the ebay keys setup or what do you reckon what would be most reasonable to start off on

> yes lets do that

**Decisions:**
- Opened ndethi/baby-arb-ke#2 for `task/repo-cleanup` (gh auth works again). Recommended Watson
  registers eBay keys in parallel; this branch is Phase 0 of `docs/live_scraping_plan.md`.
- Branched from `task/repo-cleanup`, not `origin/main`: main is still the initial commit and
  the collectors/scripts only exist on that branch. Independent of `task/ebay-browse-client`.
- Checked `~/.hermes/cron/jobs.json` before switching branches: all ten jobs paused.
- UNKNOWN is carried as `DemandSignals.unknown_reasons` (source -> reason), so a missing value
  stays `None` (already treated as missing by the aggregator) and the reason travels with it.
  When no signal at all is present the aggregator now returns confidence `UNKNOWN` and
  recommendation `UNKNOWN`, instead of `LOW`/`WATCH` with score 0.
- One merge helper (`baby_arb.demand.collect`) replaces five copies of the same merge loop;
  a collector exception becomes an UNKNOWN reason instead of being silently dropped.
- Demo values removed rather than flagged: a flag still lets numbers reach Telegram.
- Tracker fallbacks (hard-coded "popular model" base scores, default demand scores 0.55/0.65/0.67)
  are fabricated rankings; replaced with "no models found" / UNKNOWN.
- `aggregator_top5.py` resale multipliers invent a KE price from the US price; it now abstains
  until a sourced KE reference price exists. Same for the mock eBay results in
  `priority_item_sourcer.py` (the real client is on `task/ebay-browse-client`).
- Alert and brief used hard-coded FX fallbacks (145.5 / 145.0); they now use
  `baby_arb.pricing.fx` and abstain when no rate is available. Both also drop products whose
  provenance is a `*_demo` collector, because `data/cache/demand_scout/latest.json` (runtime,
  gitignored) still holds demo values from before the pause.

- The local Poetry venv had drifted from `poetry.lock` (typer 0.12.5 vs 0.16.1, the click 8.4
  break); ran `poetry sync` before testing.
- Ran `scripts/demand_check_job.py` once end to end before noticing its `main()` posts to Telegram
  when credentials exist. `.env` has none, so nothing was sent; afterwards only the functions
  were exercised.
- The FX cache is ~3,450h old and `pricing.fx.get_usdkes_rate()` returns a stale cached rate
  when the (stubbed) live fetch fails, contrary to its own "never >24h" docstring. Not changed
  here (pricing engine); alert and brief treat >24h as UNKNOWN. Flagged for Watson.
- A `ruff --fix` glob briefly touched `scripts/scrape_reddit.py`; reverted, not committed.

**Outcome:** 8 commits; 89 tests pass. Left for later phases: `priority_item_sourcer.py` still
carries hard-coded priority items and a fixed 145 FX (unreachable now that search returns
nothing; superseded by the eBay client + pricing engine), `generate_smart_baby_tech_demand.py`
word-count scoring (Phase 3), stale demo values in the gitignored
`data/cache/demand_scout/latest.json` (now filtered out; refreshed by `update_demand_signals`).
