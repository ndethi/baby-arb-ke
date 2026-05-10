<!-- Skill version: 0.1 | Last improved: 2026-05-10 | Uses: 0 -->
<!-- Status: POST-MVP. Stub only. Do not activate until shadow pilot validates margin discipline. -->

# Buyer

Execute approved purchases via per-task virtual cards.

## When to use
- Watson has explicitly approved a candidate via Telegram
- The candidate has PASS from Compliance and BUY from Pricing
- The candidate has a valid US warehouse shipping address configured

## Instructions (post-MVP)
1. Verify all preconditions:
   - Approval token from Watson (Telegram callback signed)
   - Compliance verdict PASS, age < 24h
   - Pricing verdict BUY, age < 4h (prices change fast)
   - Listing still active and price unchanged
2. Issue a single-use virtual card via Wise Business API:
   - Amount: listing_price + us_shipping + 5% buffer
   - Merchant locked to eBay (or relevant marketplace)
   - Single-use, expires 24h after issuance
3. Execute the purchase via the marketplace's Buy API or browser
   automation. Capture order_id, transaction_id, full receipt.
4. Send seller a message via marketplace messaging:
   - Thank them
   - Confirm shipping to US warehouse address
   - Request photo of label DOM if car seat
5. Record purchase in DB: candidate_id, virtual_card_id, order_id,
   amount_charged, expected_delivery, seller_id.
6. Notify Watson on Telegram with purchase confirmation.

## Constraints
- Never use a non-virtual or shared card.
- Never charge above the verified BUY ceiling.
- Never proceed without valid Approval token.
- Never auto-buy above MAX_AUTO_BUY_USD ($200) without fresh Telegram
  approval (cannot rely on a brief approval).
- Never store card details in any log, cache, or DB.

## Output format
```json
{
  "purchase_id": "uuid",
  "candidate_id": "uuid",
  "marketplace": "ebay",
  "order_id": "...",
  "virtual_card_last4": "1234",
  "amount_charged_usd": 87.50,
  "expected_delivery_us_warehouse": "2026-05-17",
  "purchased_at": "2026-05-10T14:23:00Z"
}
```

## Commit format
`feat(buyer): <description>`

## Self-improvement signals
- If virtual card declines exceed 5%: investigate funding flow.
- If listings expire between approval and purchase: tighten the
  Pricing verdict freshness window from 4h to 1h.
