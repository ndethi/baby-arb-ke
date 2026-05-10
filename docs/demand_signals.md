# Demand Signals

What the Demand Scout listens to and how signals combine into a score.

## Signal sources, ranked by purchase-intent strength

1. **Jiji marketplace data** — actual KE used market activity. Strongest
   single signal because it's where used baby goods actually trade.
2. **Jumia/Kilimall stockouts** — supply-side signal that reveals
   shortages of new equivalents.
3. **FB parenting groups in Kenya** — high purchase-intent signal.
   "Mum looking for X" is a buyer expressing intent in the next 30 days.
4. **Pigiame search frequency** — price-discovery activity, decent signal.
5. **Instagram Kenyan parent creators** — aspirational, leading indicator
   for premium items but lagging on actual purchase intent.
6. **TikTok Kenyan parent creators** — same as IG, slightly weaker
   because Kenyan baby content reach is narrower than global.

## Signal weights (initial, recalibrate from Margin Evaluator data)

```
weights:
  jiji_sold_30d:           0.30
  jiji_supply_demand_ratio: 0.20  # active listings / sold = supply tightness
  retail_stockout_weeks:   0.15
  fb_intent_score:         0.15
  pigiame_volume:          0.10
  ig_kenyan_mentions:      0.05
  tiktok_kenyan_mentions:  0.05
```

The `demand_score` is a weighted sum normalised to 0.0-1.0 across the
visible candidate set. Confidence is reduced if any high-weight signal
is UNKNOWN.

## Signal interpretations

### Jiji.co.ke
- `active_listings_count`: how many sellers are currently listing the
  product or close substitutes
- `sold_listings_30d`: from listing history (Jiji shows "sold" status)
- `median_listed_price_kes`: asking price (overstates true clearing price)
- `median_sold_price_kes`: where visible, this is the true clearing price

**Supply tightness:** `active / max(1, sold_30d) < 0.5` = tight market,
boost demand score.

### Jumia / Kilimall
- `stock`: in_stock | out_of_stock | not_listed
- `weeks_out_of_stock`: how long has this been unavailable

A new equivalent being out of stock for 4+ weeks is a strong "buyers
have nowhere to turn" signal that benefits used market sellers.

### Facebook parenting groups (KE)
Target groups (extend as we learn):
- Mums Village Kenya
- Nairobi Mums
- Kenyan Parents Network
- Mombasa Mums
- Nakuru Mums

For each group, in the last 30 days:
- `mentions`: count of posts/comments mentioning the brand or product
- `intent_score`: fraction of mentions expressing purchase intent
  ("looking for", "where can I get", "anyone selling") vs informational

### Instagram + TikTok
- `kenyan_mentions_30d`: posts by Kenyan parent creators (location-tagged
  Kenya AND audience >50% KE OR self-described Kenyan parent)
- `sentiment`: 0-1 score, positive mention rate

These are leading indicators. Weight low until validated by sales data.

## Manual signal entry (MVP mode)

Until scrapers are built, Watson enters signals via CLI:

```bash
baby-arb demand add \
  --product "NUNA PIPA Lite RX" \
  --jiji-active 3 \
  --jiji-sold-30d 11 \
  --jiji-median-sold 32500 \
  --jumia-stock out_4w \
  --fb-mentions 23 \
  --fb-intent 0.71 \
  --ig-mentions 47 \
  --tiktok-mentions 8
```

Or via Telegram conversational entry — Hermes parses a message into
the structured form.

## What NOT to use as a signal

- **Kenyan baby influencer promotional posts.** These are paid; not
  organic demand.
- **Aspirational Instagram saves on US accounts.** Not Kenyan demand.
- **Western trend forecasts.** Different market dynamics.
- **AliExpress/Temu trending products.** Different price tier and
  buyer mindset; doesn't translate to used premium goods market.

## Signal staleness

| Signal | Acceptable age |
|--------|---------------|
| Jiji active listings | 24h |
| Jiji sold 30d | 7 days |
| Jumia stock | 48h |
| FB mentions | 7 days |
| IG/TikTok mentions | 14 days |
| Pigiame | 7 days |

If any signal exceeds its age limit, mark as UNKNOWN, don't use stale data.

## Calibration

The Margin Evaluator records, for each item sold:
- demand_score at time of brief
- actual sell-through days
- actual final sale price

Quarterly: regress sell-through and price against signal components.
Update weights to match observed reality.
