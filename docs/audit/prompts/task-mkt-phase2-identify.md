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
- Found in the bot log: the third test drop (P-0003) rendered, but sending six 1-2 MB PNGs as
  one album timed out and the exception also swallowed the captions and buttons. Fixes (a
  Phase 1 bug, fixed here because the live bot runs this branch): JPEG copies for Telegram
  (PNGs stay the files to post), longer media timeouts, an album failure no longer stops the
  card, a `show P-0003` command re-sends the latest preview, and an error handler logs one line.

## 2026-11-27 · Claude Code (claude-opus-5-5) · Brave key live

**Prompt** (verbatim; key redacted):
> [REDACTED: Brave Search API key] this is the brave search key, lets restart the bot

**Decisions:**
- Key written to the gitignored `.env` (mode 600); not printed or committed.
- First live lookup found the right products but no facts: shop pages answered 404 without
  browser headers, and the 6,000-character page budget was spent on menus and carts. Now:
  browser `Accept` headers, up to 4 page tries, product-first text (JSON-LD Product, og/meta
  description, main block), and search snippets as sources when no page can be read (same
  grounding rule). Live result: batteries, material, size and a feature, each with its source.
  No Kenyan retailer listed the Huanger walker, so no price was suggested.
- The shop page said "9 months and older" while the box says 6m+: captions skip an online age
  range when the listing has one, and skip values over 60 characters. The preview shows all.

## 2026-11-27 · Claude Code (claude-opus-5-5) · details on the image

**Prompt** (verbatim):
> do we want to overlay these details we picked up online on top of the image so image is self
> explanatory, basic details and enrich the caption with more details , and then lets consider in
> the next phase if we want to directly interface with the socials (FB, IG, tiktok) api - is this
> in the pipeline

> lets start on the overlay and captions now,let me know what needs to be set up on the meta
> side of things

**Decisions:**
- Details strip (template v2): up to 3 short facts above the price on feed and story, on the
  second TikTok frame (the first stays photo, price and code). New `details` element: the
  creative checks cover it, and "hide the details" / "details bigger" are edits.
- Each fact now has a model-written `short` form (<= 24 chars) that must pass the same
  page-support check as the value; unsupported shorts are dropped. Chips prefer size,
  batteries, features; captions get up to 5 "• Label: value" bullets (short form when the
  value is long). An online age range never replaces the one from the line or the box.
- Live run found the lookup trusting a generic guess: unbranded photos gave "Baby activity
  walker", and Brave returned another product whose specs reached the caption. Lookup now
  runs only for a brand read from the photos or a name the admin typed or confirmed; a
  correction clears the model's brand. The preview says when the lookup was skipped.
- Meta setup: listed for the operator in chat (spec section 12); nothing set up from here.
