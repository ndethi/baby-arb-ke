# Operating Runbook

Daily, weekly, and monthly cycles for running the pipeline.

## Weekly cycle

### Sunday 18:00 UTC — Demand Scout (cron)
- Scrapers run (post-MVP); manual entry runs Watson
- Output: `data/cache/demand_scout/latest.json`
- If MVP, Hermes pings Watson on Telegram: "Time to enter demand
  signals for the week. Send a brief or paste the signal blocks."

### Sunday 17:00 UTC — Margin Evaluator (cron)
- Reconciles last week's sales
- Posts summary to Telegram
- Opens issue if drift pattern detected

### Monday 06:00 UTC — Trend PM (cron)
- Reads demand report
- Composes weekly brief
- Posts to Telegram with action buttons
- Opens PR `task/weekly-brief-YYYY-MM-DD`

### Monday 08:00 UTC — Sourcing Scout (cron)
- Searches eBay per priority item
- Runs Compliance + Pricing on each candidate
- Posts ranked list to Telegram
- 6 candidates max, sorted by margin descending

### Mon-Sat — Watson decisions
- Approve / decline candidates via Telegram
- Manual buy in MVP (post-MVP: Buyer agent)
- Daily watch-list ping: "These 3 listings drop tomorrow"

### Sunday 20:00 UTC — Daily docs sync (cron)
- Sync any updated SKILL.md from `~/.hermes/skills/` to repo
- Write progress note to `docs/progress/YYYY-MM-DD.md`
- Open PR `chore(docs): daily sync YYYY-MM-DD`

## Monthly cycle

### First Sunday — Trendsetter (post-MVP)
- Forward-looking: items not yet in KE that we could introduce
- Different motion from arbitrage: marketing-led, longer cycle time
- 3-5 recommendations per month, no buy obligation

### First Monday — Curator review
- Reviews skill performance over last 4 weeks
- Updates weights, descriptions, instructions
- Bumps skill version numbers
- Reports to Telegram

### Last Sunday — Compliance refresh
- Refresh KEBS restricted items list
- Refresh counterfeit-prone brand list
- Refresh static safety blocks
- All via PR

## Daily ops (lightweight)

### Morning ping
- Hermes posts a one-line status: "3 watchlist items, 0 alerts,
  pricing engine healthy"

### Auction-end alerts
- 30 minutes before any watchlist auction ends, ping Telegram with
  current price and pricing verdict

### Cache health
- Daily 04:00 UTC: refresh CPSC recall cache
- Daily 04:30 UTC: refresh FX rate
- If either fails 2 days in a row: alert Watson

## Health check — run weekly

```bash
baby-arb health
# Outputs:
# - eBay API: connected, X queries used / Y limit
# - CPSC cache: age, freshness OK/STALE
# - FX rate: age, USD/KES = X
# - DB: rows in candidates / verdicts / sales
# - Last brief: date, n_priorities
# - Last margin eval: date, n_evaluated, n_OFF
```

## Failure modes

| Symptom | Likely cause | Action |
|---------|--------------|--------|
| Sourcing returns 0 candidates | Brief queries too narrow | Trend PM reruns with broader queries |
| Pricing skips >70% | Brief target prices unrealistic | Update demand floor data |
| Compliance BLOCKs >40% | New recall surge or rules drift | Review BLOCK reasons distribution |
| Margin Evaluator drift > 10pp on 3+ items | Model bias | Open `pricing-drift` issue |
| FX moved >5% since last refresh | Geopolitical / market event | Force refresh + replay open verdicts |
| DHL rates changed | Carrier update | Update `intl_shipping.py` rate card |

## Telegram command reference

For Watson:
- `/brief` — show this week's brief
- `/candidates` — current sourcing candidates
- `/approve <id>` — approve a candidate (MVP: just notes intent)
- `/decline <id>` — decline a candidate
- `/skip <id>` — drop from this week's brief
- `/eval` — show last week's margin evaluation
- `/health` — health check
- `/skill new <name>` — trigger Skill Generator
- `/curator now` — early curator run

For Hermes (responses):
- Brief notification with inline buttons
- Candidate cards with margin breakdown
- Margin Evaluator weekly summary
- Compliance alert when a BLOCK happens on a watchlist item
- Daily morning status

## Git workflow

```bash
# Watson never commits to main
git checkout -b task/<slug>
# ... agent or human work ...
git push -u origin task/<slug>
# Open PR via gh CLI or web
gh pr create --fill
# Review, merge, delete branch
gh pr merge --squash
git checkout main
git pull
git branch -d task/<slug>
```

## Money flow checks (pre-buy phase)

Before any real-money operation begins:
- [ ] Wise Business account funded
- [ ] Virtual card issuance tested with $1 transaction
- [ ] eBay buyer account in good standing
- [ ] US warehouse address confirmed
- [ ] DHL account set up with credit terms
- [ ] M-Pesa Daraja sandbox tested
- [ ] Pesapal merchant account active
- [ ] Insurance policy on inbound shipments

This is the gate between shadow pilot and real operations.
