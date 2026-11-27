# Prompt log · task/mkt-phase1-drop-preview

## 2026-11-27 · Claude Code (claude-opus-5-5)

**Prompt** (verbatim):
> done the ping but didnt quite get a response  on telegram, could we check that it did on. here,
> then lets go on and on this question Merge order: #2, #3, #4, #5, all squash. Should I start
> Phase 1 (drop, preview, edits, calendar) now, stacked on #5, or wait until you've reviewed it?
> lets recommend best course of action given the spec we are looking to achieve

> got pong, go ahead with phase 1

**Decisions:**
- Stacked on `task/mkt-phase0-foundations` (#5): Phase 1 needs its tables, screen, llm.py and
  bot allow-list, and nothing in Phase 1 publishes, calls Meta or messages a buyer.
- Spec source: ENGINE_SPEC.md is on `task/marketing-engine-spec` (#4), read from there.
- Pipeline logic lives in `marketing/pipeline.py`; the bot (`bot/handlers.py`) and the CLI
  (`mkt ...`) are thin callers, so every step is testable and runnable without Telegram.
- Price: stored as the admin gave it. The parser only reads a price from the first token and
  the bot asks when it is missing. Model captions are rejected if they show any shilling amount
  other than the admin's price or reference price; a model edit may set the price only to a
  number the admin typed. The 3x-buy check is a warning on the preview.
- Safety: BLOCK is final (listing BLOCKED, approve refuses). Recall lookup is still Phase 2, so
  every own/seller item is REVIEW with `recall_not_checked` and needs an explicit override
  button. An edit that changes title or notes re-screens; a new REVIEW reason needs a fresh
  override, a BLOCK closes the listing (EDITING -> BLOCKED added to the transitions).
- Item name: Phase 1 has no model ID, and the spec's example caption line has no item, so the
  bot asks "what is it?" (spec section 1 step 3, "asks if unsure"). Optional `buy 600` and
  `ref 8500` tokens feed the pricing warning and the "new in Nairobi" anchor; neither is ever
  invented.
- Edit parsing: deterministic rules first (34 fixture phrasings, no model), the model only for
  text the rules don't cover, then a clarifying question. Every applied op goes to
  `edit_events` with before/after and `parsed_by`.
- Rendering: Playwright + Jinja2 HTML template. Playwright 1.65's driver needs macOS 13.5 and
  this Mac runs 13.3, so pinned `~1.59.0`, which matches the cached Chromium build 1217 and
  falls back to the system Chrome (`channel="chrome"`, present on GitHub's Ubuntu runners). No
  browser download. Brand fonts aren't in `assets/fonts/` yet (spec section 12): system font
  stack for now. Golden images are per platform (`tests/golden/darwin/`); other platforms skip
  the pixel comparison but still run the creative checks.
- Calendar: `config/calendar.yaml` copied from the spec. A slot is a batch (max N posts at the
  slot time); `min_gap_minutes` applies between different occupied times on a shared channel.
  Specials replace that kind's regular slot on their date and count on off-rhythm days.
- Stored times: new `UTCDateTime` column type (SQLite dropped tzinfo and stored Nairobi wall
  time, which broke slot matching).
- `cal tick`: reminders with files at slot time, MISSED 2 h after the reminder, Mon 08:00 /
  daily 18:30 / Wed 18:00 / Sun 16:00 messages once per day via bot_state flags; silent when
  idle or paused. The bot runs tick every 5 minutes itself (and right after Now), so no Hermes
  cron entry was added; `baby-arb mkt cal tick` is ready for one and is idempotent.
- Album handling: Telegram delivers album photos as separate updates processed one at a time,
  so the wait for the rest of the album runs in a background task.
- Found while testing: the earlier `/ping` got no reply because nothing was polling; IDs were
  read from getUpdates and written to `.env` (not logged here).

**Outcome:** see commits on this branch. Not done: brand fonts/logo (operator), Hermes cron
entry (asked first), group privacy setting for albums (operator, see PR).

## 2026-11-27 · Claude Code (claude-opus-5-5) · launchd

**Prompt** (verbatim):
> privacy disabled, try a drop in the group now and lets also launch a launchd job so we can keep
> this alive
>
> in terms of the brand fonts - lets think through what tools we could use through this pipeline
> to bootstrap a brand guide but park that for later

**Decisions:**
- getMe confirms `can_read_all_group_messages: true`. A bot can't send itself a drop (Telegram
  doesn't deliver a bot's own messages to it), so the group test needs an admin to post the album.
- `scripts/install_bot_launchd.sh` writes `~/Library/LaunchAgents/ke.babyreshop.bot.plist`
  running `baby-arb bot run` from this working copy (logs in `~/Library/Logs/babyreshop/`).
  KeepAlive restarts on crash (checked with kill -9) and leaves a clean stop stopped.
  `ProcessType=Interactive`: with default throttled I/O the first start took ~2 min in OpenSSL
  certificate loading. The script waits for bootout to finish; bootstrap otherwise fails with
  error 5.
- The agent runs whatever branch is checked out here, like the Hermes cron jobs.
- Brand guide tooling: parked as asked.

**Outcome:** agent installed and running; script committed.
