# Landed Cost Model

Every component of the cost from "listed on eBay" to "in a Kenyan
buyer's hands". This is the single source of truth for the formula.

## Inputs

| Field | Source | Notes |
|-------|--------|-------|
| `listing_price_usd` | marketplace | the buy-it-now or current bid + estimated final |
| `us_shipping_usd` | marketplace | seller → US warehouse |
| `us_warehouse_state` | warehouse config | DE/MT/NH/OR = no sales tax |
| `seller_state` | listing | for sales tax sourcing rule (destination-based for most) |
| `item_weight_lb` | listing or product DB | actual > listed > estimated |
| `item_dimensions_in` | listing or product DB | length, width, height |
| `declared_value_for_intl_usd` | listing_price | basis for KE customs CIF |
| `fx_rate_usdkes` | FX provider | TTL 12h, refresh on stale |

## Formula

```
us_subtotal_usd
  = listing_price_usd
  + us_shipping_usd
  + us_sales_tax_usd                    [if warehouse state has sales tax]
  + warehouse_handling_usd              [consolidator per-item fee]

intl_shipping_usd
  = max(actual_weight, dim_weight) * rate_card[carrier][weight_band]
  where dim_weight = (L * W * H) / 139    [DHL standard divisor in inches]

cif_usd
  = us_subtotal_usd + intl_shipping_usd + insurance_usd

ke_duty_kes        = cif_kes * 0.25       [25% on most baby goods]
ke_idf_kes         = cif_kes * 0.035      [3.5% IDF]
ke_rdl_kes         = cif_kes * 0.02       [2% RDL]
ke_vat_kes         = (cif_kes + ke_duty_kes) * 0.16   [16% on duty-paid value]

ke_last_mile_kes   = sendy_or_g4s_quote_kes
ke_storage_kes     = days_stored * daily_rate_kes      [if any]

total_landed_kes
  = (cif_usd * fx_rate_usdkes)
  + ke_duty_kes
  + ke_idf_kes
  + ke_rdl_kes
  + ke_vat_kes
  + ke_last_mile_kes
  + ke_storage_kes
```

## Margin

```
margin_kes = reference_ke_sale_price_kes - total_landed_kes
margin_pct = margin_kes / total_landed_kes
```

A candidate is BUY-eligible only if:
1. `margin_pct >= MARGIN_FLOOR_PCT` (default 50%)
2. `confidence in {HIGH, MEDIUM}`
3. Compliance verdict is PASS

## US sales tax handling

The destination state determines sales tax for most US transactions:
the state where the warehouse is located.

| Warehouse state | Sales tax | Notes |
|-----------------|-----------|-------|
| Delaware | 0% | best choice for high-volume |
| Oregon | 0% | West coast option |
| Montana | 0% | rare for 3PLs |
| New Hampshire | 0% | East coast option |
| New Jersey | 6.625% | clothing/baby products often exempt |
| Florida | 6% | popular for Mercari sourcing |
| California | 7.25%+ | avoid |
| Texas | 6.25% | avoid |

Some baby items are exempt in some states regardless (clothing in NJ
and PA, breastfeeding equipment in many states). The
`pricing/us_costs.py` module owns the lookup table.

## Confidence levels

- **HIGH**: actual weight from warehouse, fresh FX (<6h), seller-confirmed
  DOM if car seat, observed KE sale prices from 5+ recent transactions.
- **MEDIUM**: estimated weight from product DB, FX 6-12h old, KE
  reference from 2-4 transactions.
- **LOW**: weight estimated from category averages only, FX > 12h, or
  KE reference from 1 transaction or asking-price-only data. ABSTAIN.

## Common cost drivers (where margin goes to die)

1. **International shipping is dimensional-weight dominated.** A
   stroller box weighs 15 lb but ships at 35 lb dim weight. Always use
   `max(actual, dim)`.
2. **KE customs is on CIF, not item price.** Adding $40 of shipping
   adds $10+ of duty/VAT/IDF/RDL.
3. **FX moves.** USD/KES drifted 8% in 2025. Hold no more KES than
   needed for 60 days of operations; convert in batches.
4. **Storage fees.** Consolidators charge $1-5/day after a free window.
   Slow inventory eats margin compounding.
5. **Sales tax.** A 7% sales tax on a $100 item is a 14pp margin hit
   if your floor is 50% — that's the difference between BUY and SKIP.

## Worked example

Item: NUNA PIPA Lite RX infant car seat, used like-new
- listing_price_usd = 180.00
- us_shipping_usd = 22.00 (seller in TX → warehouse in DE)
- DE has no sales tax → us_sales_tax_usd = 0
- warehouse_handling_usd = 5.00
- us_subtotal_usd = 207.00
- weight 9 lb, dims 18x18x24 in → dim_weight = 56 lb
- intl_shipping_usd via DHL Express to NBO: 56 lb @ ~$8/lb = 448
  (ouch — dim-weight-dominated; consider sea freight if not urgent)
- cif_usd = 207 + 448 = 655
- fx 145.5 KES/USD → cif_kes = 95,302
- ke_duty_kes = 95,302 * 0.25 = 23,826
- ke_idf_kes = 3,336
- ke_rdl_kes = 1,906
- ke_vat_kes = (95,302 + 23,826) * 0.16 = 19,060
- ke_last_mile_kes = 1,500
- total_landed_kes = 95,302 + 23,826 + 3,336 + 1,906 + 19,060 + 1,500
                   = 144,930

Reference KE sale: NUNA PIPA Lite RX used median on Jiji = 32,500 KES.

margin_kes = 32,500 - 144,930 = NEGATIVE (-112,430)
margin_pct = -77%

Verdict: SKIP. The dimensional weight on a car seat from Texas via DHL
Express makes this entire trade unworkable.

**This is exactly why the pricing agent matters.** The intuition "used
NUNA car seat, big demand, US is cheap" leads to a catastrophic loss
when you actually run the math. Either consolidate by sea freight
(brings shipping per item down 60-80%) or only source car seats local
to a 0%-sales-tax warehouse with a feeder shipping system.

## Engine versioning

Any change to the formula bumps the engine version in
`src/baby_arb/pricing/__init__.py`. Margin Evaluator records which
version was used for each prediction so drift analysis can attribute
errors to model changes vs reality.
