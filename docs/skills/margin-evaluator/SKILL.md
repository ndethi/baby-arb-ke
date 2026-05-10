<!-- Skill version: 0.1 | Last improved: 2026-05-10 | Uses: 0 -->

# Margin Evaluator

Reconcile actual sale margin against Pricing Engineer's prediction.
The feedback loop that keeps the pricing model honest.

## When to use
- An item has been sold (KE buyer payment confirmed) and shipped to buyer
- Cron-triggered weekly Sunday 17:00 UTC for batch reconciliation
- Watson sends: "How accurate were last week's margin predictions"

## Instructions
1. Read SOUL.md.
2. For each item that completed its lifecycle (purchased → shipped →
   received → KE-listed → KE-sold → KE-buyer-paid → KE-buyer-received):
   STEP 1 — Compute actual margin
     actual_margin = (final_sale_kes - all_actual_costs_kes) / all_actual_costs_kes
   Where all_actual_costs includes everything Pricing predicted PLUS:
     - storage fees if held >30 days
     - dispute/refund partial losses
     - additional last-mile fees
     - FX losses if KES held instead of converted
   STEP 2 — Compare to predicted
     drift_pp = (actual_margin - predicted_margin) * 100
   STEP 3 — Categorise drift
     ON-TARGET: |drift_pp| <= 5
     SLIGHT: 5 < |drift_pp| <= 10
     OFF: |drift_pp| > 10
3. For OFF items, identify the cost driver responsible. Common drivers:
   - actual_weight differed from estimate by >15%
   - international_shipping rate changed since prediction
   - FX rate moved >2% between purchase and sale
   - additional fees not modelled (e.g., warehouse rehandling)
4. Aggregate weekly stats per category:
   - n_sold, mean_predicted_margin, mean_actual_margin, mean_drift_pp
   - count of OFF items per cause
5. Write report to `docs/progress/margin_eval_YYYY-MM-DD.md`.
6. If any cost driver appears in 3+ OFF items in a single week, open
   a GitHub issue tagged `pricing-drift` with proposed model fix.
7. Send weekly summary to Telegram.

## Constraints
- Never adjust a Pricing prediction retroactively. The drift is the
  signal — losing the original record loses the signal.
- Never include items still in-flight in actuals.
- Never blend categories — strollers and car seats drift differently.

## Output format
Markdown report with a summary table:
```
| Category | n | Predicted % | Actual % | Drift pp | Worst driver |
|----------|---|-------------|----------|----------|--------------|
| stroller | 4 | 54.2        | 49.1     | -5.1     | weight       |
| car seat | 2 | 61.8        | 60.4     | -1.4     | -            |
```

## Commit format
`eval(margin): weekly reconciliation YYYY-MM-DD`

## Self-improvement signals
- If actual margins consistently undershoot predictions by 5pp+ for
  4 consecutive weeks: the model has a systematic bias. Time to
  investigate fees not currently modelled.
- If FX drift causes 3+ OFF items in a week: tighten FX cache TTL
  or add a hedge step before purchase.
