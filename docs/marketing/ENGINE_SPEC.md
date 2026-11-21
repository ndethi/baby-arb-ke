# babyReShop KE Marketing Engine: spec

Version 1.1, 21 Nov 2026 (1.1 adds the content calendar, section 4). Lives in the repo as `docs/marketing/ENGINE_SPEC.md`.
Owner: Ndethi. Builder: Claude Code. Runtime: Hermes plus a local bot process.

The operator's flow in section 1 is the product. Everything else in this spec serves it.
When this spec and an older doc disagree (including the "Hybrid Claude + Hermes" handoff
and the posting scaffold's auto-pricing), this spec wins.

---

## 1. The vision in one flow

1. **Drop.** An admin sends item photos plus one line to the shop's Telegram bot.
2. **Screen.** The bot blocks never-sell items and checks recalls before doing any work.
3. **Identify.** The bot identifies brand and model from the photos and asks if unsure.
4. **Price.** The admin's price is used. The bot only warns (for example, below 3x the buy price).
5. **Render.** The bot builds a feed graphic (4:5), a story graphic (9:16), a short vertical video for TikTok and Reels, and captions per platform. All are built around the real photos.
6. **Preview.** The bot sends the bundle back to Telegram with a proposed calendar slot and the buttons ✅ Approve, ✏️ Edit, ❌ Reject, ⏩ Now, 🕒 Move, ⏭ Skip.
7. **Edit loop.** On ✏️ the admin describes changes in plain words. The bot applies them, re-renders and sends the bundle again. Every change is logged as drift.
8. **Schedule and publish.** On ✅ the post is queued in its calendar slot (section 4). At slot time the bot publishes to Instagram and the Facebook Page and sends the TikTok post to the admin's phone. Publishing goes through Meta's API, with no browser automation. Until Phase 3 the bot sends a reminder with the files instead, and the admin posts by hand.
9. **Boost.** The admin boosts by hand. The bot never touches spend.
10. **Watch.** An ad watcher reads results daily, alerts when a stop rule trips and recommends what to change at the end of a run.
11. **Sell.** The admin types `sold P-0007` (or taps SOLD). Inventory updates, a SOLD graphic is made and posts are updated.
12. **Talk.** DMs arrive in Telegram. Safe questions are answered automatically. Everything else gets a suggested reply that the admin sends with one tap, or the admin answers in the Instagram app.
13. **Learn.** A weekly report turns drift, ad results, sales and best posting times into proposed changes to defaults and to the calendar, which the admin approves.

## 2. Principles and hard rules

- **Humans decide.** Nothing is published, nothing is sent to a buyer (beyond the safe automatic tier), and no spend changes without an admin action in Telegram.
- **Real photos only.** No AI-generated product images or video. Graphics frame the real photos and never alter the item.
- **Safety first.** BLOCK items can never be approved. REVIEW items and unknown recall status need an explicit admin "yes, override".
- **Deterministic by default.** Rendering, database work, publishing, scheduling and reports are plain Python with no model calls. A model is used only where judgement is needed (section 10).
- **Meta account safety.** Use official APIs only, read data no more often than needed (ads once a day), no scraping, no bulk messaging.
- **No new subscriptions.** Use free tiers and local tools: Telegram bot API, Meta developer app, Playwright, FFmpeg, SQLite, Cloudflare Tunnel (free). The only running cost is model calls, which have a daily cap.
- **Data protection (Kenya DPA 2019).** Keep minimal buyer and seller data. Delete seller details 30 days after SOLD. Send marketing messages only to people who opted in.
- **One source of truth.** One SQLite database in `baby-arb-ke`, extending the posting module's store. No second repo, no second database.
- **Automate only after doing it twice by hand.** Each phase ships something usable before the next starts.

## 3. Phases

Each phase ends with something the admins use that week. Later phases depend only on
earlier ones.

| Phase | Name | What the admin gets | Depends on |
|---|---|---|---|
| 0 | Foundations | Bot answers `/ping`. Database migrated. Meta app created. | none |
| 1 | Drop, preview, approve, calendar | Photos in, approved feed and story PNGs out, edits logged as drift. Every approved post gets a calendar slot; the bot reminds at slot time with the files and the admin posts by hand. | 0 |
| 2 | Identify and video | Model ID, recall check, TikTok/Reels MP4 in the preview bundle. | 1 |
| 3 | Publish and sell | Posts publish to IG and FB at their slot. `sold` updates inventory and posts. Seller (declutter) listings path. | 1 (2 optional) |
| 4 | Ad watcher | Daily ad readout, stop-rule alerts, end-of-run recommendation. | 3 |
| 5 | Inbox bridge | DMs in Telegram, safe auto-answers, one-tap suggested replies, funnel counts. | 3 |
| 6 | Learning loop | Weekly drift and performance report, default and best-time changes, price-drop nudges, opt-in drop list, swipe file. | 1, 4, 5 |

Target pace is one phase per week. Phases 4 and 5 can be built in parallel.

---

### Phase 0: Foundations

**Build**
- Install the posting scaffold (`src/baby_arb/posting/`) into the repo if it isn't there yet, and keep its 34 tests green.
- Create `src/baby_arb/marketing/` (layout in section 8).
- Migrate the database to the schema in section 7. Use Alembic or the existing SQLModel pattern, whichever the repo already uses.
- Telegram bot process (`baby-arb bot run`) with `/ping`, `/help` and an allow-list of admin Telegram user IDs. Messages from anyone else are ignored.
- `.env` keys: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ADMIN_IDS`, `META_APP_ID`, `META_APP_SECRET`, `META_PAGE_ID`, `META_IG_USER_ID`, `META_SYSTEM_USER_TOKEN`, `META_AD_ACCOUNT_ID`, `LLM_PROVIDER`, `LLM_DAILY_CAP_USD`.
- Meta developer app inside business portfolio "babyReShop KE" (business_id 1173124822322578), with a system user token. The operator does this step by hand (checklist in section 12).

**Decision Claude Code must settle first:** can the Hermes Telegram gateway send media albums and inline buttons, and receive button presses? If yes, the bot runs as a Hermes skill. If not (recommended default), a thin `python-telegram-bot` process owns the Telegram UI and calls the `baby-arb` CLI. Hermes then handles the model calls and the scheduled jobs.

**Done when:** `/ping` replies to admins only, the migration runs on a copy of the live database, and CI is green.

---

### Phase 1: Drop, preview, approve

**Intake.** An admin sends 1 to 6 photos as one album. The caption is a single line:

```
<price> [grade A|B|C] [age range] [notes]        own stock
#seller <price> <seller name> [notes]             declutter listing (Phase 3 completes this path)
```

Example: `2000 B 0-36m washed, small mark on strap`.
If the price is missing, the bot asks for it. The bot never guesses a price.

**Pipeline**
1. Create the listing with code `P-000N` (own stock) or `L-000N` (seller listing) and status `INTAKE`.
2. Run the safety screen (existing scaffold): keyword and category check against the never-sell list. BLOCK stops the pipeline and the bot says why.
3. Pricing check: record the admin's price as `price_source = admin`. If `buy_price` is known and price is below 3x buy, attach a warning to the preview. Nothing is changed automatically.
4. Caption drafts (model call): Instagram/Facebook caption and TikTok caption from the house template. The first line gives price, model and age range. Every caption includes the listing code and one call to action ("DM P-0007 to buy").
5. Render (Playwright, HTML/CSS templates in `assets/templates/`):
   - `feed_4x5.png` 1080x1350: hero photo, price badge, code, condition badge, CTA strip, "Seller listing" tag on L-codes.
   - `story_9x16.png` 1080x1920: same elements, story-safe margins.
   - `tiktok/` 1080x1920 photo-post set: one 9:16 frame per photo, price and code on the first frame.
   - For own stock, a "new in Nairobi from KES X" anchor appears only when the admin gave a reference price. No invented anchors.
6. Creative checks as code (`baby-creative-eval`): minimum text size at phone scale, exactly one CTA, price visible, code visible, seller tag present on L-codes, no text over the item's flaw areas when flagged. Failures are fixed by the renderer or shown on the preview.
7. Slot: the calendar proposes the next free slot for the post's kind (section 4) and writes a `schedule` row with status `PROPOSED`.
8. Preview: Telegram album (feed, story, TikTok set, later the video) plus the captions and a slot line such as `Slot: Fri 27 Nov, 12:30 (listing 2/4)`, with buttons ✅ Approve (takes the proposed slot) / ✏️ Edit / ❌ Reject / ⏩ Now / 🕒 Move / ⏭ Skip. Status changes to `PREVIEW`.

**Edit loop**
- ✏️ asks "What should change?". The admin replies in plain words, for example "price bigger, drop 'washed', use photo 3 as main".
- A model call turns the text into edit operations from a closed list:
  `set_field(field, value)`, `swap_photo(slot, photo_n)`, `reorder_photos([...])`, `resize(element, up|down)`, `move(element, position)`, `toggle(element, on|off)`, `set_template(name)`, `rewrite_caption(platform, instruction)`, `crop(photo_n, focus)`.
- The bot echoes the parsed operations ("I'll: make price badge larger, remove 'washed' from caption, set photo 3 as hero") and applies them, re-renders and sends a new preview (round N+1).
- If the text can't be mapped to the list, the bot asks a short clarifying question. It does not guess.
- Every operation is written to `edit_events` (section 7), with the raw text, round number and before and after values. This is the drift log.

**Approve and reject**
- ✅ sets status to `APPROVED`, stores the final asset paths and moves the `schedule` row to `QUEUED` (listing status `SCHEDULED`). ⏩ Now queues it for immediate posting. ⏭ Skip keeps it `APPROVED` with no slot.
- At slot time (Phases 1 and 2) the bot sends a reminder with the final files and captions, and the admin posts by hand: Business Suite for IG and FB, the TikTok app or TikTok Studio for TikTok. The admin replies `posted P-0007` or taps Posted, and the row becomes `POSTED` (listing `LIVE`). If it isn't marked within 2 hours, it becomes `MISSED` and the bot asks whether to re-slot it.
- ❌ asks for a one-line reason (optional), sets `REJECTED` and logs the reason as drift with op `reject`.

**Done when:** three real items have gone from drop to approved PNGs, at least one through an edit round, `edit_events` holds the edits, and one full week of slots has run with reminders, `posted` marks and the Monday and daily queue messages.

---

### Phase 2: Identify and video

**Model ID.** A vision model call on the photos returns brand, model, category, age or weight range and a confidence score.
- Confidence of 0.8 or higher fills the fields and shows them on the preview, marked "(auto)".
- Below 0.8, the bot asks: "Looks like a Graco FastAction Fold, right? Reply with the model or 'skip'."
- The admin's words always override the model's guess. Overrides are logged as drift (`op = correct_model`).

**Recall check.** Replace the CPSC client stub with a real lookup on brand and model. PASS / REVIEW / BLOCK goes into `safety_verdicts`. Unknown counts as REVIEW and needs an explicit admin override.

**Video (FFmpeg, `render_reel`)**
- 9:16 1080x1920 MP4, 15 to 30 seconds (fits both TikTok's 15 to 45 s target and Reels under 60 s), 30 fps, H.264 `-preset veryfast`, rendered with no music. Sound is added at posting from each platform's own library (Instagram audio; TikTok's Commercial Music Library on the Business account). Never post a watermarked TikTok as a Reel or the reverse.
- Pan-and-zoom over each photo (about 3 seconds each), with price and code on the opening frame and the CTA on the closing frame.
- Captions burned in, using the same brand fonts as the static templates.
- Optional later: edge-tts voiceover (sw-KE or en-KE voices), off by default.
- The video joins the preview album, and edit operations can target it (`set_field`, `reorder_photos`, `trim(seconds)`).

**Done when:** a preview bundle includes the MP4, model ID is right on at least 4 of 5 test items, and a known recalled model gets blocked in tests.

---

### Phase 3: Publish and sell

**Publish on ✅**
- Instagram: post the feed image (or a carousel of the rendered feed graphic plus the raw photos) and the Reel through the Instagram Content Publishing API. Publish the story through the API if the account supports it; otherwise send it to the admin's phone to post.
- Facebook Page: photo post through the Graph API with the same caption.
- TikTok: the bot sends the MP4 and TikTok caption to the admin, who posts it from the TikTok app. Revisit the Content Posting API once an audited app is worth the effort, because unaudited apps can only post privately.
- Timing comes from the calendar: the `cal tick` job publishes each `QUEUED` row at its slot. ⏩ Now publishes straight away, and `✅ later 18:30` stays as a manual override. Content posts (`/post teaser|tip|behind`) publish the same way.
- The reminder from Phases 1 and 2 is replaced by a confirmation with links. TikTok still arrives as a reminder with files, because it is posted by hand.
- Each publication is written to `publications` with platform, post ID and URL. The bot replies with the links.
- On an API failure, the bot retries once, then sends the files for manual posting and logs the error. It never retries in a loop.

**Sold and inventory**
- `sold P-0007 [price] [buyer channel]` or the SOLD button on the listing card. Status changes to `SOLD` and a `sales` row is written.
- The bot renders a SOLD version of the feed graphic and offers to add a "SOLD" line to the caption on IG and FB (one tap, API edit where supported). It also offers a SOLD story.
- `collected P-0007` closes the sale. `back P-0007` reopens a sale that fell through.
- `/stock` lists what's live, with days since posting.

**Seller (declutter) listings**
- Same pipeline with `#seller`. Before publishing, the bot also needs the seller's name, WhatsApp, consent to share it with buyers, and the M-Pesa fee code. Fee rows go to `seller_fees`.
- A buyer who DMs an L-code gets the seller's WhatsApp, with the seller's consent.
- 30 days after SOLD, a scheduled job deletes the seller's personal details and keeps the listing and fee records.

**Done when:** one own-stock item and one seller listing go from drop to live on IG and FB through ✅, and a `sold` command updates inventory and produces the SOLD graphic.

---

### Phase 4: Ad watcher

**Admin side, unchanged:** the admin boosts by hand from the app or Business Suite.

**Link.** The watcher finds new ads daily through the Marketing API (read-only, `ads_read`). It matches each ad to a listing code by the boosted post ID. If it can't match, it asks the admin "Which listing is this boost for?".

**Daily readout (one scheduled run, 08:00 Nairobi)**
- Per active ad: goal, spend to date, reach, frequency, results for the goal (conversations, profile visits), cost per result, saves, and DMs that mention the code (from Phase 5).
- Compared with the shop's median for unboosted posts and with earlier boosts.
- Writes `ad_snapshots` and sends a short Telegram summary only when something changed.

**Stop rules (defaults, editable with `/rules`)**
- Messages goal: KES 600 spent and 0 conversations → alert "consider stopping".
- Profile-visits goal: cost per profile visit above 2x the shop's running median after KES 600 → alert.
- Frequency above 3 → alert "audience is saturated".
- The item SOLD while its ad is running → alert to switch the ad to a brand post or stop it.
- Alerts recommend only. The admin acts in Ads Manager.

**End-of-run report (when an ad ends or is stopped)**
- What happened: the funnel from reach to collected for that listing.
- Verdict, picked from: keep this setup, change creative, change audience, change goal, change price, don't boost this kind of item.
- The reason, citing the numbers. A model call writes the explanation; the numbers and the verdict rules are deterministic.
- Stored in `ad_runs.verdict` and fed to Phase 6.

**Done when:** a real boost is linked to its listing, one daily readout and one end-of-run report have been sent, and stop rules are covered by unit tests on fixture data.

---

### Phase 5: Inbox bridge

**Transport.** Instagram and Facebook messages arrive through the Messenger and Instagram messaging webhooks, using a free Cloudflare Tunnel to the local machine. Fallback: poll the conversations API every 5 minutes. WhatsApp stays manual until there is a shop line; then it moves to the WhatsApp Cloud API through the same bridge.

**In Telegram:** each new conversation becomes a thread card showing the platform, the person's handle, the message, any detected listing code, and a suggested reply with buttons [Send] [Edit] [I'll answer in app].

**Answer tiers**
| Tier | Examples | Behaviour |
|---|---|---|
| T0 automatic | "Is P-0007 available?", "price?", "where is pickup?", "how do I list my item?" | Answered automatically from the database. The admin sees a copy. |
| T1 suggested | Condition questions, delivery, holding an item, seller-listing questions | The model drafts a reply. The admin taps Send or Edit. |
| T2 human only | Haggling, payment problems, complaints, anything unclear | No draft beyond "noted". Pings both admins. |

- T0 replies use fixed templates filled from the database, with no free model text.
- Meta's 24-hour window is respected. Outside it, the bot only tells the admin.
- Quiet hours (default 22:00 to 07:00): T0 still answers, everything else waits.
- Funnel counting: conversations, codes mentioned and "price agreed" (admin taps a button) go into `funnel_events`. This replaces most hand-logging.
- Opt-in: when a sale closes, the bot can suggest asking "Want first pick of our next drop?". A yes is stored in `contacts` with date and channel.

**Done when:** a test DM gets a T0 answer, a T1 draft is sent with one tap, and funnel counts appear in the daily readout.

---

### Phase 6: Learning loop

- **Weekly report (Sunday 19:00, before the Sunday review):** top edit operations from drift, approval rate on the first preview, model ID corrections, sell-through and days to sell by category, boost verdicts, cost per conversation and per sale. Also exported as CSV in `data/exports/` to upload to the Claude Project for strategy review.
- **Best times:** a section of the weekly report reads Instagram Insights online-follower hours and per-slot results, and proposes edits to `config/calendar.yaml` (for example "move `listing` to 13:00"). Accepting goes through `defaults_history`. Slot times are first reviewed after two weeks of data.
- **Default proposals:** when the same edit appears 3 or more times in 2 weeks (for example, enlarging the price badge), the report proposes changing the default. The admin taps Accept, the template or config changes, the template version goes up, and the change is logged in `defaults_history`.
- **Price-drop nudges:** after 5 days unsold, the bot proposes a drop (default 10 to 15%) or a bundle with another live item, and the admin taps yes or no. Never automatic.
- **Drop list broadcast:** a weekly "Thursday drop" message to opted-in contacts only, drafted by the bot and sent after admin approval, at a few messages a minute, never in bulk.
- **Swipe file:** a weekly, admin-triggered browser read of up to 10 Meta Ad Library pages for Nairobi baby-resale competitors. Hooks and offers are written to `knowledge/SWIPE_WAREHOUSE.md`.
- **Next-stage outreach (later):** a "your baby's next stage" message for opted-in buyers 45 to 60 days after purchase. Build it only once there are 20 or more opted-in buyers.

---

## 4. Content calendar

Every approved post gets a proposed slot, scheduled messages keep the week full, and slot
times move as the data comes in. Nobody has to remember the weekly rhythm.

### Weekly rhythm (Nairobi time)

| Day | IG + FB | TikTok | Slot kind |
|---|---|---|---|
| Mon 19:00 | "This week's finds" teaser carousel | Same, as a photo post | `teaser` |
| Tue 12:30 | Declutter listings, batch 1 | Listings as photo posts | `listing` |
| Wed 19:00 | Parent help (size guide, carrier fitting, how we recall-check) | Native video of the tip | `tip` |
| Thu 19:00 | **The Drop**: our picks carousel + Reel | Drop video | `drop` |
| Fri 12:30 | Declutter listings, batch 2 | Listings as photo posts | `listing` |
| Sat 12:30 | Behind the scenes, pickups, buyer reviews (with consent) | Native video: haul / "what KES 2,000 gets you" | `behind` |
| Sun | No posts. Weekly review. | No posts | none |

Weekly volume: 5 IG/FB feed posts plus daily Stories; 5 TikToks (3 photo posts from the
same shoot, 2 native videos). The 12:30 and 19:00 times are starting guesses, reviewed after
two weeks of Insights data (Phase 6).

### Config: `config/calendar.yaml`

This file is the calendar. Changing the rhythm means editing it or accepting a Phase 6
proposal that edits it. No slot times are hard-coded anywhere else.

```yaml
timezone: Africa/Nairobi
channels: [instagram, facebook, tiktok]
slots:
  drop:     {days: [thu], time: "19:00", max: 6}        # own picks (P-codes)
  listing:  {days: [tue, fri], time: "12:30", max: 4}   # seller listings (L-codes)
  teaser:   {days: [mon], time: "19:00", max: 1}
  tip:      {days: [wed], time: "19:00", max: 1}
  behind:   {days: [sat], time: "12:30", max: 1}
blackout_days: [sun]
min_gap_minutes: 90          # between two feed posts on the same channel
lookahead_days: 14
specials:                    # one-off dated slots that override the weekly rhythm
  - {date: 2026-11-27, kind: listing, time: "12:30", label: "Black Friday roundup"}
  - {date: 2026-12-03, kind: drop,    time: "19:00", label: "Drop 3, gift edition"}
```

### Module: `src/baby_arb/marketing/calendar.py` (deterministic, no model calls)

- `load_config() -> CalendarConfig`, validated with pydantic.
- `slot_kind_for(listing) -> str`: P-code → `drop`, L-code → `listing`.
- Content posts (teaser, tip, behind) start with `/post <kind>` (photos or video plus one line). They get codes `C-000N` and go through the same render, preview, edit and approve loop, without pricing or recall steps.
- `next_free_slot(kind, after=now) -> Slot`: the earliest slot of that kind within `lookahead_days` where the filled count is below `max`, not on a blackout day, and respecting `min_gap_minutes`. Specials count as slots of their kind on their date.
- `week_view(start) -> list[SlotStatus]`: filled, empty and capacity per slot, for the Monday message and `/week`.
- Handles a full slot (roll to the next day of that kind), a full week (roll to the next week), Nairobi time with no DST, and a slot already in the past (skip it).

### Scheduled jobs (Hermes cron, Nairobi time)

| When | Message to "babyReShop Ops" |
|---|---|
| Every 5 min | `baby-arb mkt cal tick`: fire due reminders or publishes, mark `MISSED` |
| Mon 08:00 | This week's slots: filled, empty, which slots need stock |
| Daily 18:30 | Tomorrow's queue, so either admin can change anything the night before |
| Wed 18:00 | "Drop tomorrow: N slots still empty" (only if the drop is under half full) |
| Slot time | Phases 1 and 2: reminder with files to post. Phase 3 on: publish, then confirm with links |
| Slot + 2 h | Phases 1 and 2: `MISSED` nudge if not marked posted |
| Sun 16:00 | Sunday review prompt (feeds the Phase 6 weekly report at Sun 19:00) |

Jobs send nothing when there is nothing to say. `/pause` stops them all. Nothing is queued
without an admin approve, and either admin can approve, move or skip.

### Format rules the renderer must respect

| | IG + FB | TikTok |
|---|---|---|
| Listing photos | Carousel 4:5, 1080x1350 | Photo post 9:16, 1080x1920 |
| Video | Reel 9:16, under 60 s | 9:16, 15 to 45 s, never a watermarked repost |
| Caption | Brand, model, price in line 1 | Title with item and price, short description |
| Hashtags | 5 or fewer | 3 to 5 |
| Sound | Instagram's own audio | Commercial Music Library only (Business account) |

### Before the bot exists

The same Telegram group works by hand from this week: drop photos there, either admin (or the
`babyreshop-drop-to-draft` skill) builds the post, and it is scheduled in Business Suite at the
slot time from the rhythm table. TikTok goes up from its app or TikTok Studio.

## 5. Telegram interface

**Chats:** a private group "babyReShop Ops" with both admins and the bot. The admin allow-list applies to commands and buttons.

**Commands**
```
(album + caption)           new listing
/stock                      live listings, days posted, status
/week                       this week's slots: filled / empty / capacity
/post teaser|tip|behind     start a content post, slotted to its day
/slots                      show calendar.yaml (edits only by file or accepted proposal)
move P-0007 fri 19:00       move to a slot (warns if over max or off-rhythm)
skip P-0007                 take off the calendar, keep APPROVED
posted P-0007               mark a manual post done (Phases 1-2)
/item P-0007                listing card with buttons
sold P-0007 [price] [ch]    mark sold
collected P-0007            close sale
back P-0007                 reopen
price P-0007 1800           change price (re-render offered)
/ads                        current ad readout
/rules                      view and edit stop rules
/inbox                      open conversations
/report                     run the weekly report now
/pause  /resume             stop or start automatic T0 replies and scheduled jobs
```

**Preview card buttons:** ✅ Approve (takes the proposed slot) · ✏️ Edit · ❌ Reject · ⏩ Now · 🕒 Move · ⏭ Skip.
**Listing card buttons:** 💰 Price · 🏷 SOLD · 📊 Stats · ✅ Posted (Phases 1-2).

## 6. Listing lifecycle

```
INTAKE -> SCREENED -(BLOCK)-> BLOCKED
                   -(REVIEW: needs override)-> SCREENED
SCREENED -> RENDERED -> PREVIEW <-> EDITING
PREVIEW -> REJECTED
PREVIEW -> APPROVED -> SCHEDULED -> LIVE
APPROVED -> APPROVED (skip: no slot)
SCHEDULED -> APPROVED (missed, not re-slotted)
LIVE -> SOLD -> COLLECTED -> ARCHIVED
SOLD -> LIVE (back)
LIVE -> ARCHIVED (withdrawn)
```
Every transition is written to `listing_events` with actor (admin ID or `system`) and time.

`SCHEDULED` points at a `schedule` row, which has its own states:
`PROPOSED -> QUEUED -> POSTED`, `QUEUED -> MISSED -> QUEUED (re-slotted) | SKIPPED`, `PROPOSED|QUEUED -> SKIPPED`.
Schedule transitions are also logged to `listing_events`.

## 7. Data model (SQLite, one database)

Extend the posting module's store. Claude Code reconciles names with what exists and keeps existing data.

| Table | Key columns |
|---|---|
| `listings` | code (P-/L-), kind (own/seller), status, title, brand, model, model_source (auto/admin), model_confidence, category, age_range, grade, condition_note, buy_price, price, price_source, ref_new_price, seller_id, template_version, created_at, live_at, sold_at |
| `photos` | listing_code, n, path, hash, is_hero |
| `listing_events` | listing_code, from_status, to_status, actor, at |
| `safety_verdicts` | listing_code, verdict (PASS/REVIEW/BLOCK), reasons, recall_source, override_by, at |
| `renders` | listing_code, round, asset (feed/story/reel/sold), path, template_version, at |
| `edit_events` (drift log) | listing_code, round, raw_text, op, target, before, after, parsed_by, at |
| `publications` | listing_code, platform, post_id, url, kind (feed/story/reel/tiktok-manual), published_at, status |
| `ad_runs` | ad_id, listing_code, goal, daily_budget, start, end, total_spend, results, cost_per_result, verdict, verdict_reason |
| `ad_snapshots` | ad_id, date, spend, reach, impressions, frequency, results, profile_visits, conversations, saves |
| `conversations` | id, platform, handle, listing_code, tier, status, last_inbound_at |
| `messages` | conversation_id, direction, text, tier, sent_by (auto/admin), at |
| `funnel_events` | listing_code, platform, stage (reach/profile_visit/dm/price_agreed/paid/collected), count, source, date |
| `sales` | listing_code, price, channel, sold_at, collected_at |
| `sellers` | id, name, whatsapp, consent_share, created_at, purge_after |
| `seller_fees` | listing_code, seller_id, fee, mpesa_ref, paid_at |
| `contacts` | id, name, channel, handle_or_phone, opt_in, opt_in_at, interest_stage, last_purchase_code |
| `schedule` | id, listing_code (P-/L-/C-), kind, slot_at, channels, status (PROPOSED/QUEUED/POSTED/SKIPPED/MISSED), proposed_by (system/admin), moved_from, reminded_at, created_at |
| `defaults_history` | key (including `calendar.*`), old_value, new_value, reason, accepted_by, at |
| `llm_calls` | purpose, model, tokens_in, tokens_out, cost_usd, at |

No children's names or birth dates are stored. `interest_stage` is a coarse band such as "0-6m".

## 8. Repo layout

```
baby-arb-ke/
  src/baby_arb/
    posting/                 existing scaffold (intake, screen, captions, store)
    marketing/
      bot/                   Telegram UI: handlers, cards, buttons, allow-list
      intake.py              album + caption parsing
      identify.py            vision model ID (Phase 2)
      safety.py              wraps posting screen + recall client
      render/
        static.py            Playwright HTML -> PNG
        reel.py              FFmpeg pan-and-zoom -> MP4
        checks.py            creative checks (baby-creative-eval)
      edits.py               plain words -> edit operations, apply, log drift
      calendar.py            slots, next_free_slot, week_view, tick (deterministic)
      publish/
        meta.py              IG + FB Graph API
        tiktok.py            manual handoff now, API later
      inventory.py           sold / collected / back / stock
      ads/
        watcher.py           Marketing API reads, snapshots
        rules.py             stop rules (deterministic)
        verdict.py           end-of-run verdict + explanation
      inbox/
        bridge.py            webhooks / polling
        tiers.py             T0/T1/T2 classification and templates
      reports/
        weekly.py            drift + performance report, CSV export
      llm.py                 single gateway for all model calls, daily cap, logging
  config/
    calendar.yaml            the content calendar (section 4)
  assets/
    raw/  templates/  ready/  audio/  fonts/
  knowledge/
    BRAND_GUIDE.md  SWIPE_WAREHOUSE.md
  data/
    baby_arb.db  exports/
  docs/marketing/
    ENGINE_SPEC.md  (this file)
  docs/skills/<name>/SKILL.md   repo copies of Hermes skills
```

**Hermes skills (live copies in `~/.hermes/skills/`, repo copies in `docs/skills/`)**
| Skill | Role |
|---|---|
| `baby-drop-pipeline` | Runs phases 1 and 2 for a new album through the CLI |
| `baby-creative-eval` | Creative checks plus a model review of the preview |
| `baby-ad-watcher` | Daily readout and end-of-run verdict |
| `baby-inbox` | T1 drafts and T2 escalation |
| `baby-weekly-report` | Sunday report and default proposals |
| `baby-resale-swipe` | Weekly Ad Library read (Phase 6) |

## 9. CLI (what Hermes and the bot call)

```
baby-arb mkt intake --album <dir> --line "<caption>"
baby-arb mkt render <code> [--round N]
baby-arb mkt edit <code> --text "<admin words>"
baby-arb mkt approve <code> [--at HH:MM]
baby-arb mkt publish <code>
baby-arb mkt sold|collected|back <code> [...]
baby-arb mkt cal next <kind>
baby-arb mkt cal week [--start YYYY-MM-DD]
baby-arb mkt cal assign <code> [--at "fri 19:00"]
baby-arb mkt cal move|skip|posted <code> [...]
baby-arb mkt cal tick                  cron every 5 min; idempotent
baby-arb mkt ads pull | ads rules | ads verdict <ad_id>
baby-arb mkt inbox pull | inbox reply <conv_id> --text "..."
baby-arb mkt report weekly [--export]
baby-arb bot run
```
Every command works without Telegram, so it can be tested and run by hand.

## 10. Where models are used (and nowhere else)

| Purpose | Phase | Input | Output |
|---|---|---|---|
| Caption drafts | 1 | listing fields, house template | IG/FB and TikTok captions |
| Edit parsing | 1 | admin's words, current state | edit operations (closed list) |
| Model ID | 2 | photos | brand, model, category, range, confidence |
| Creative review | 1 | rendered PNGs | pass or issues (on top of code checks) |
| Ad verdict explanation | 4 | numbers + rule verdict | short reason text |
| DM tiering and T1 drafts | 5 | message, listing data | tier + draft |
| Weekly narrative | 6 | report numbers | short summary |

All calls go through `marketing/llm.py`, which enforces `LLM_DAILY_CAP_USD`, logs to `llm_calls` and degrades without failing: when over the cap, the bot asks the admin instead of calling the model.

## 11. Testing and quality

- Unit tests for intake parsing, pricing warnings, stop rules, tiering, state transitions.
- Calendar: a full slot rolls to the next day of that kind; a full week rolls to next week; blackout day; past slot skipped; specials honoured; `min_gap_minutes` enforced; `move` over `max` warns but allows.
- `cal tick` is idempotent: running it twice never double-posts or double-reminds.
- Golden test of the Monday week-view message.
- Golden-image tests for templates: render fixtures and compare against stored PNGs within a tolerance.
- Fixture-based tests for edit parsing (20 or more real phrasings to expected operations).
- Meta and Telegram clients mocked in tests. A `--dry-run` flag on publish and reply commands.
- ruff and mypy strict clean, Conventional Commits, `task/<slug>` branches, one PR per phase.

## 12. Operator setup checklist (done by hand)

- [ ] Telegram: create the bot with BotFather, create the "babyReShop Ops" group, add both admins.
- [ ] Facebook Page linked to @babyreshopke (Settings > Linked accounts), Page added to the business portfolio.
- [ ] Meta developer app in the portfolio: Instagram Graph API, Pages API, Marketing API (read), Instagram and Messenger messaging. System user with a long-lived token.
- [ ] Liebchen accepts the Business Suite invite (expires mid-December).
- [ ] An always-on machine for the bot (laptop or spare) and a Cloudflare account for the tunnel (Phase 5).
- [ ] Model provider for Hermes chosen and daily cap set.
- [ ] Brand fonts and logo in `assets/fonts/` and `assets/templates/`.

## 13. Open decisions

| Decision | Default until decided |
|---|---|
| Hermes gateway or thin bot for the Telegram UI | Thin bot for UI, Hermes for model calls and scheduled jobs |
| Who can approve: either admin or both | Either admin |
| Auto T0 replies on from day one of Phase 5 | On, with `/pause` |
| Quiet hours | 22:00 to 07:00 |
| Shop WhatsApp number | None yet; WhatsApp stays manual |
| Buffer | Dropped in favour of Meta's API; revisit for TikTok scheduling |
| Model provider and daily cap | Operator's existing Hermes provider, USD 1/day |
| Slot times | 12:30 and 19:00 as in section 4, reviewed after two weeks of Insights |
| Stop-rule thresholds | As in Phase 4, reviewed after the first 3 boosts |

## 14. Kickoff prompt for Claude Code (Phase 0 + 1)

```
Read CLAUDE.md, AGENTS.md, SOUL.md, docs/architecture.md, src/baby_arb/posting/
and docs/marketing/ENGINE_SPEC.md. The spec wins where docs disagree.

Plan first, no code: Phase 0 and Phase 1 only. Phase 1 includes the content
calendar (section 4): config/calendar.yaml, calendar.py, the schedule table,
the slot line and Approve/Now/Move/Skip buttons, the move, skip, posted,
/week and /post commands, and `baby-arb mkt cal tick` on Hermes cron with the
Monday, daily, Wednesday and Sunday messages. Phase 1 sends reminders with files at slot time.
1. Settle the Hermes-gateway vs thin-bot decision (section 3, Phase 0) and say why.
2. Map section 7 tables onto the posting store; list migrations.
3. List files to create under src/baby_arb/marketing/ for these phases.
4. Test plan, including golden-image and edit-parsing fixtures.
Rules: admin price is never changed; BLOCK is never approvable; no publishing,
no Meta calls and no messages to buyers in these phases; all model calls go
through marketing/llm.py with the daily cap.
After I approve the plan, build on task/<slug> branches (never main), keep ruff/mypy strict and CI green,
and open one PR per phase.
```
