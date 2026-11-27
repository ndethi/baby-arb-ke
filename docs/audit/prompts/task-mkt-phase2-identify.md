# Prompt log · task/mkt-phase2-identify

## 2026-11-27 · Claude Code (claude-opus-5-5)

**Prompt** (verbatim):
> 1. photo add with caption works great, but would be even better if we could use a vision engine
> to read whats on the photo and augment the caption with scraped details - can do this in two
> phases if branding/model details available in the photo we could use that otherwise read the
> photo and look up online for more metadata

> use brave search, i'll get the key

**Decisions:**
- Stacked on `task/mkt-phase1-drop-preview` (ndethi/baby-arb-ke#6). This is the identify half of
  spec Phase 2; the real recall lookup and the reel come next.
- Vision: the configured model (OpenRouter `nemotron-3.5-super-vl:free`) through llm.py, so the
  daily cap and logging apply. Checked live on the test walker photo before building (brand
  HUANGER, "Music Walker", confidence 0.95). Photos are downscaled to 1024 px JPEG.
- The model called the walker "Baby Walker", which is a BLOCK phrase. The model now picks a
  category from a fixed list (push_walker vs seated_walker, ...) and the screen sees our words
  for that key, never the model's text. Unsure walker type -> seated_walker (BLOCK).
- Brand/model only from visible text. Confidence >= 0.8 fills the title "(auto)"; lower asks
  "looks like X, right?" ('yes' accepts). Corrections are drift (`correct_model`), as the spec
  says. Identify and lookup run once per listing (stored in `listings.details`, migration 0004).
- Brave lookup (key from the operator; `BRAVE_SEARCH_API_KEY`): specs query, top 2 matching
  pages fetched as text, one model call extracts at most 5 facts. A fact is kept only if it
  cites a fetched page and its numbers and most words are on that page; no prices. Page text
  is treated as data. Marketplaces (Jiji, Facebook, eBay) are skipped.
- KE price: a KSh amount read by regex from a Kenyan retailer result that names the item
  (Jumia, Kilimall, ...), shown with its source. Only an admin tap ("Use KES X as 'new from'")
  sets `ref_new_price`, through the normal edit path. Never inferred, never automatic.
- Brave calls capped per Nairobi day (`BRAVE_DAILY_CALL_CAP`, default 50).

**Outcome:** see commits on this branch. Brave lookup untested live until the key is in `.env`.
