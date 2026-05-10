"""Marketplace sourcing clients.

MVP: eBay Browse API only. Mercari, FB Marketplace, OfferUp post-MVP.

Status: skeleton for Hermes/Copilot to flesh out per docs/skills/sourcing-scout/SKILL.md.

Hermes handoff:
    Build src/baby_arb/sourcing/ebay/client.py:
      - httpx.AsyncClient with tenacity retry on 5xx
      - OAuth2 client-credentials grant for the Browse API
      - search_items(query, filters) -> list[raw_listing]
    Build src/baby_arb/sourcing/ebay/parser.py:
      - parse a raw eBay listing into a BuyCandidate
      - extract brand, model, condition, weight if listed, dims if listed
    Build src/baby_arb/sourcing/ebay/search.py:
      - turn a SourcingBrief priority item into a Browse API query
      - apply hard filters (seller feedback, ships to US warehouse, etc.)
    Then wire it all into src/baby_arb/sourcing/runner.py with:
      - run_brief(brief) -> list[(candidate, compliance_verdict, pricing_verdict)]
"""
