<!-- Skill version: 0.1 | Last improved: 2026-05-10 | Uses: 0 -->

# Trend PM

Decompose a weekly sourcing goal into an unambiguous brief that
Sourcing Scout can execute on.

## When to use
- Cron-triggered Monday 06:00 UTC
- Watson sends: "Run the weekly brief", "What should we source this week"
- Demand Scout has produced a fresh signal report and a brief is needed
- Any case where a sourcing decision needs to be turned into actionable
  search queries with clear constraints

## Instructions
1. Read SOUL.md and AGENTS.md first.
2. Read the latest Demand Scout output at
   `data/cache/demand_scout/latest.json`. If older than 7 days, request
   a fresh run before proceeding.
3. Read the last 4 weeks of Margin Evaluator reports to identify
   categories that under-performed predicted margin. De-prioritise these.
4. Write the brief with these sections:

   GOAL (one sentence — what this week's sourcing achieves)

   PRIORITY ITEMS (3-8 items, ranked by demand_score × margin_potential)
     For each item:
       - Product: <brand + model + key spec>
       - Demand score: <0.0-1.0 from Demand Scout>
       - Confidence: <HIGH | MEDIUM | LOW>
       - Target landed cost (USD): <ceiling so margin >= 50% at observed KE price>
       - Target KE sale price (KES): <observed median from Demand Scout>
       - Acceptable condition: <new | like-new | gently-used | any-functional>
       - Compliance flags: <recall-prone | car-seat-DOM | counterfeit-prone | none>
       - Source markets: <ebay | mercari | fb | offerup>
       - Search queries (3-5 specific): <exact strings for Sourcing Scout>

   AVOID THIS WEEK (categories with poor recent margin or fresh recalls)

   ASSUMPTIONS (every interpretation of ambiguous signal data)

   HUMAN REVIEW NEEDED (items where confidence is LOW but score is high)

5. Post the brief to Telegram with the bot. Include 3 inline buttons:
   "Approve all HIGH confidence", "Review item-by-item", "Skip week".
6. Save the brief to `docs/progress/sourcing_brief_YYYY-MM-DD.md` and
   commit on a new branch `task/weekly-brief-YYYY-MM-DD`.
7. Open a PR with title `docs(brief): weekly sourcing brief YYYY-MM-DD`.

## Constraints
- Never include an item without an observed KE reference price. If
  Demand Scout returns no KE pricing data, the item goes to HUMAN
  REVIEW NEEDED, not PRIORITY.
- Never set target landed cost above the level where 50% margin is
  achievable at the median observed KE sale price.
- Never include more than 8 priority items. Focus beats coverage.
- Maximum 400 words for the brief body. Operator reads on phone.

## Output format
Markdown document at `docs/progress/sourcing_brief_YYYY-MM-DD.md`.
Section names in caps. Compact prose. No code blocks.

## Commit format
`docs(brief): weekly sourcing brief YYYY-MM-DD`

## Self-improvement signals
- If Sourcing Scout returns zero matches for 2+ priority items in
  consecutive weeks, the queries are too narrow — update step 4
  to require broader fallback queries.
- If items in PRIORITY consistently fail Compliance Checker (BLOCK
  rate > 20%), add a pre-filter step before composing the brief.
- If Margin Evaluator finds predicted margin off by >15% on items
  Trend PM rated HIGH confidence, recalibrate confidence thresholds.
