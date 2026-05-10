<!-- Skill version: 0.1 | Last improved: 2026-05-10 | Uses: 0 -->
<!-- Status: POST-MVP. Stub only. -->

# Logistics Coordinator

Manage the chain from US warehouse intake through Nairobi last-mile.

## When to use
- A purchase has been made and tracking number is available
- A shipment has arrived at US warehouse and needs consolidation
- KE customs documentation is needed for an outbound shipment
- A delivered item needs last-mile dispatch in KE

## Instructions (post-MVP)
1. Track US-side delivery via marketplace tracking + warehouse webhook.
2. On warehouse intake, capture:
   - Actual weight (warehouse scale, supersedes our estimate)
   - Actual dimensions
   - Photos of received condition
   - Any damage report
3. If actual weight/dims differ from estimate by >15%, trigger Pricing
   re-evaluation before paying for international shipping.
4. Consolidate up to N items per outbound shipment to amortise customs
   minimum fees. Wait up to 7 days for consolidation.
5. Generate KE customs invoice and packing list. CIF value = sum of
   actual costs (not retail).
6. Book DHL Express, Aramex, or sea freight based on:
   - Total weight + volume
   - Days-to-revenue priority (high-margin items: air; bulk strollers: sea)
   - Customer wait tolerance (none have pre-orders in MVP)
7. On KE arrival: pay customs, IDF, RDL, VAT. Trigger storage fees clock.
8. Dispatch last-mile via Sendy/Glovo/G4S based on buyer location and
   item value (high-value: G4S with insurance).

## Constraints
- Never ship a shipment with declared CIF value below actual cost
  (under-declaration = customs fraud).
- Never combine items in a way that triggers a higher duty bracket.
- Never use sea freight for car seats (weight-to-value ratio favours air).
- Never delay a shipment more than 14 days for consolidation savings.

## Output format
Per-shipment record stored in DB. Telegram updates on each milestone.

## Commit format
`feat(logistics): <description>`

## Self-improvement signals
- If actual weight differs from estimate by >15% on 20%+ of items,
  the Sourcing Scout's estimation is unreliable — invest in a
  product DB with verified weights/dims.
- If customs delay > 5 days on 10%+ of shipments, the customs broker
  documentation needs improving.
