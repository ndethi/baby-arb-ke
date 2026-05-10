<!-- Skill version: 0.1 | Last improved: 2026-05-10 | Uses: 0 -->
<!-- Status: POST-MVP. Stub only. -->

# Listing Writer

Generate KE-facing listings for Jiji, Instagram, and the storefront.

## When to use
- A shipment has arrived in KE and items are ready for listing
- An existing listing needs to be refreshed (price, photos, copy)
- Watson sends: "Write a Jiji listing for the Doona we received"

## Instructions
1. Read SOUL.md and the brand voice notes in `docs/brand_voice.md`
   (create on first run).
2. For each item, generate three variants tuned per channel:
   - Jiji: factual, KES-priced, pickup/delivery options stated
   - Instagram: lifestyle copy, hashtags for KE parent audience
   - Storefront: full spec sheet, condition grade, included accessories
3. Required content for every listing:
   - Brand + model + year
   - Condition grade (A: like-new, B: gently-used, C: functional)
   - Original retail (USD or KES, marked as such)
   - Compliance certifications cleared (no recall, DOM verified for
     car seats — "DOM 2023, 4 years remaining usable life")
   - What's included, what's not
   - Honest photos (inspected by Logistics on arrival)
4. Pricing: pull from the price strategy set by Pricing Engineer for
   this item. Never invent a price.
5. Never imply features the unit doesn't have. Never reuse stock photos
   of a different item.

## Constraints
- Never claim "new" on used items.
- Never omit known damage or wear.
- Never write copy implying the item is recalled-cleared without the
  Compliance verdict on file.
- No AI-marker phrases. Plain Kenyan-friendly English (no "delve",
  "it's worth noting", em dashes, marketing gloss).
- Use KES throughout for buyer-facing copy. USD only as reference.

## Output format
Three markdown files per item under `data/cache/listings/<item_id>/`:
`jiji.md`, `instagram.md`, `storefront.md`.

## Commit format
`docs(listing): <item brand model> ready for publish`

## Self-improvement signals
- If listings sit unsold past 45 days, A/B test copy changes.
- If buyers consistently ask the same question pre-purchase, add the
  answer to the listing template.
