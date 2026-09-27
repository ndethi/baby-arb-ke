# Live data collection plan

Status: proposal for Watson's review (2026-09-27). Nothing here is built yet; demo-fed cron jobs
paused 2026-09-27 (see Decisions).

## Where we are

Hermes already runs this repo's scripts on a schedule (`~/.hermes/cron/jobs.json`):

| Job | Schedule | Script | State |
|---|---|---|---|
| baby-arb-demand-update | every 6 h | `scripts/demand_check_job.py` | active |
| test-multi-source-demand | every 6 h | `scripts/collect_multi_source.py` (via skill) | active |
| smart-baby-tech-demand-gen | every 6 h | `scripts/generate_smart_baby_tech_demand.py` | active |
| baby-arb-daily-alert | daily 07:00 | `generate_alert` skill | active |
| aggregator-top5-weighted | daily 03:00 | `scripts/aggregator_top5.py` | active |
| baby-arb-weekly-brief | Mon 06:00 | brief generator | active, last output 2026-08-24 (empty priority list) |
| pump / stroller / toy trackers | hourly | `scripts/scrape_*.py` | paused since 2026-06-01 |

**Most of what these jobs report comes from demo data, not live data.**

- `src/baby_arb/demand/collectors/{jiji,facebook,instagram_public,tiktok_public}.py`
  return hard-coded numbers keyed on the product name (e.g. every stroller:
  12 Jiji listings, 8 sold, KES 15,000 median), tagged `entered_by="*_demo"`.
  This breaks the hard constraint "never invent KE retail prices".
- `collect_multi_source.py` forum and Reddit collectors are also demo.
  `demand_check_job.py` injects "baseline demo data" when sources are thin.
- `aggregator_top5.py` resale multipliers are "adjusted for demo to achieve
  >=50% margin".
- `scripts/sourcing/priority_item_sourcer.py` returns mock eBay listings with
  made-up item URLs.
- The genuinely live fetches are HTML scrapes of eBay/Mercari/OfferUp/Facebook
  Marketplace search pages, BabyCenter, Mumsnet and Reddit RSS, all with a
  spoofed browser User-Agent. Facebook Marketplace needs a login, so it yields
  nothing, and Reddit blocks most subreddits (`docs/references/may-2026-reddit-access-findings.md`).
- Cron jobs run from the development working copy, so switching branches can
  break them.

## Principles

1. **No fabricated values.** A source that fails or is not built returns
   `UNKNOWN` with a reason. Downstream scoring abstains on UNKNOWN.
2. **Provenance on every number:** source, URL, fetched_at, method (api /
   html / manual), and a hash of the stored raw response.
3. **Official APIs first**, HTML only where no API exists, never behind a login.
   Honour robots.txt, identify ourselves in the User-Agent, rate-limit
   (at most 1 request every 2 s per host), and cache.
4. **Snapshot, then derive.** Store raw daily snapshots and compute signals
   from their differences over time. This is how we get "sold in 30 days" from
   sites that never publish it.
5. **No personal data.** Strip seller names and phone numbers at parse time.
6. **One entry point.** Cron calls `baby-arb collect ...`, not ad-hoc scripts.

## Sources, in priority order

| # | Source | Answers | Method | Notes |
|---|---|---|---|---|
| 1 | **eBay Browse API** | US supply: price, condition, ships-internationally | Official REST, OAuth client credentials | HERMES_HANDOFF item 1. Needs eBay developer keys (`EBAY_APP_ID` is not set in `.env` yet). Active listings only; sold comps need Marketplace Insights (restricted access). |
| 2 | **Jiji.co.ke** | KE demand + KE used resale price | HTML of category/search pages, daily snapshot | robots.txt allows general crawling (query-string pages are only disallowed for Bingbot). Search redirects (302), so a spike must confirm the stable URLs. Listings that disappear between snapshots give a sold-in-30-days proxy; the median asking price gives the resale estimate. Apify actor is the fallback if the HTML is JS-rendered or blocked. |
| 3 | **Jumia / Kilimall** | KE new-retail price ceiling, stockouts | HTML product pages, weekly | Low volume; a stockout on a popular SKU is a demand signal. |
| 4 | FB parenting groups, IG, TikTok | KE social pull | Manual entry now; Apify/Phyllo later | Out of scope until budget; keep `demand add` manual path. |
| 5 | Reddit, BabyCenter, Mumsnet | US/UK parent sentiment, model names | Keep (Watson, 2026-09-27) | Not KE demand; Reddit mostly blocked. Weight low in scoring. |
| 6 | Mercari, OfferUp, FB Marketplace HTML | US supply | Keep (Watson, 2026-09-27) | Brittle; FB needs login, so expect UNKNOWN there. |

## Architecture

```
config/watchlist.yaml          brand+model queries per category (replaces per-script lists)
        │
baby-arb collect --source jiji|jumia|ebay
        │
src/baby_arb/collect/<source>/
   fetch.py   → data/raw/<source>/<date>/<query>.html|json   (gitignored, hashed)
   parse.py   → Observation(source, query, item_id, price, currency, condition,
                            fetched_at, url, raw_sha256)
        │
src/baby_arb/storage/          SQLite observations + run records (HANDOFF item 2)
        │
src/baby_arb/demand/derive.py  snapshots → DemandSignals (active count, sold-30d proxy,
                               median price, confidence, UNKNOWN reasons)
        │
aggregator → Trend PM brief → pricing engine + compliance gate → Telegram
```

- **Tests:** parsers run against captured HTML/JSON fixtures in `tests/fixtures/`;
  HTTP is mocked with respx. No live network in the test suite.
- **Health:** every run writes a run record (queries, items parsed, failures).
  Telegram warns on zero parsed items or a parse-failure spike, which usually
  means the site layout changed.
- **Deployment:** crons run from a separate worktree pinned to the latest
  release tag (`git worktree add ../baby-arb-ke-live v0.2.0`), updated only
  when a release is cut (see `docs/skills/release/SKILL.md`). Development
  branches can no longer break production jobs.

## Phases

| Phase | Work | Exit criterion |
|---|---|---|
| 0. Stop fabricated signals | Collectors return UNKNOWN instead of demo values; alerts say "no live data" where true; Watson decides whether to pause the demo-fed cron jobs | No `*_demo` values reach Telegram |
| 1. US supply | eBay Browse API client + storage layer (HANDOFF 1-2) | `baby-arb collect --source ebay` stores observations for the watchlist |
| 2. KE demand | Jiji spike (URL scheme, rendering, block rate), then snapshot collector + derive; Jumia reference prices | 14 days of snapshots; sold-30d proxy and median price per watchlist item |
| 3. Rewire | Cron jobs call the CLI from the live worktree; move `scripts/scrape_*` and `collect_multi_source` behind the CLI, remove demo paths; weekly brief resumes on real data | Brief lists items with provenance, or says why it can't |
| 4. Social | Apify/Phyllo for IG/TikTok/FB when budget allows | Cost per signal known |

## Decisions for Watson

1. ~~Pause the demo-fed cron jobs now?~~ **Decided 2026-09-27: yes.** Paused with
   `hermes --profile default cron pause <id>`: baby-arb-demand-update, test-multi-source-demand,
   baby-arb-daily-alert, baby-arb-weekly-brief, baby-arb-weekly-demand-gen,
   aggregator-top5-weighted. Resume with `hermes --profile default cron resume <id>` only once
   Phase 0 lands. Still running: smart-baby-tech-demand-gen (live fetches, but its scores are
   word counts in raw HTML, e.g. "marketplace" on Facebook's login page; pause pending decision).
2. ~~eBay developer keys?~~ **2026-09-27: none yet.** Register a free app at developer.ebay.com
   (production keyset; Browse API needs only an application token, default 5,000 calls/day).
   Production keys require the Marketplace Account Deletion notification: we store no eBay user
   data, so apply for the exemption. Until keys arrive, Phase 1 is built against respx fixtures and
   eBay sandbox; the HTML scrapers stay, but note eBay robots.txt disallows `/sch/i.html?_nkw=`.
3. ~~Jiji: direct HTML or Apify?~~ **2026-09-27: direct HTML snapshots.** Apify stays the fallback
   only if the spike shows JS rendering or blocking.
4. ~~Drop Reddit/BabyCenter/Mumsnet and Mercari/OfferUp/FB scrapers?~~ **2026-09-27: keep them.**
   Phase 3 migrates them behind `baby-arb collect` with the same provenance/UNKNOWN rules instead
   of retiring them.
