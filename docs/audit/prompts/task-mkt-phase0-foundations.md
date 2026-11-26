# Prompt log · task/mkt-phase0-foundations

## 2026-11-21 · Claude Code (claude-opus-5-5)

**Prompt** (verbatim; the bot token in item 5 is redacted):
> yes lets retarget #4 to main since this is the new direction the project is taking then from the
> engine spec i will paste in the prompt claude asked i have you run from here
> [ENGINE_SPEC section 14 kickoff prompt: plan Phase 0 + 1, then build per phase]

> 1. build the scaffold
> 2. hold off on recall checks
> 3. recommend free Nemotron or otherwise available model call, check my current hermes config for
> keys if cant find let me know after this run
> 4. whats the value of adding alembic, avoiding bloat on first run but if harder to bolt on after
> then lets go ahead
> 5. [REDACTED: Telegram bot token]

**Decisions:**
- Retargeted ndethi/baby-arb-ke#4 (spec) from `master` to `main`.
- Thin `python-telegram-bot` process, not a Hermes skill. Checked the installed Hermes source:
  its Telegram adapter can send albums and a gateway *plugin* can hoist custom callback handlers,
  but that hooks private internals, and skills run every message as a model turn (cost, cap,
  non-determinism). Hermes keeps scheduling via `script` + `no_agent` cron jobs (no model call;
  empty stdout is silent).
- No posting scaffold existed anywhere (repo history, ~/Downloads zip, ~/baby-resale-ops), so it
  is built fresh in `src/baby_arb/posting/`: tables, store, safety screen. Screen rules come from
  the babyReShop drop-to-draft skill (BLOCK/REVIEW lists) and compliance-checker step 5.
  "walker" alone is REVIEW (push walker vs seated walker); seated/baby walkers are BLOCK.
- Recall lookup held off (answer 2). Spec section 2 says unknown recall status needs an admin
  override, so every item screens at least REVIEW with reason `recall_not_checked` until Phase 2.
- Models: Hermes `.env` already has NVIDIA and OpenRouter keys (values not read into the repo).
  Default NVIDIA hosted `nvidia/nemotron-3-super-120b-a12b` (the model Hermes points at), fallback
  OpenRouter `nvidia/nemotron-3.5-super-vl:free` (from the `campaign` profile). Free tiers cost
  $0, so llm.py also enforces a daily call-count cap besides LLM_DAILY_CAP_USD. OpenAI-compatible
  HTTP via httpx: no new SDK.
- Alembic added (answer 4): bolting it on later means hand-writing a baseline that exactly matches
  a live schema and stamping it; doing it now costs one dependency and four files.
- Did not write the bot token into `.env`: credentials are entered by the operator. Suggested
  revoking it in BotFather because it was pasted into chat.
- `poetry` had disappeared from the machine (likely a Homebrew Python upgrade). `brew install`
  builds from source on this macOS, so stopped it and installed Poetry 2.5.1 into
  `~/.local/share/poetry-venv`, linked at `~/.local/bin/poetry`.
- CI baseline: fixed the 24 mypy strict errors (annotation-only; pydantic mypy plugin for HttpUrl
  fields). commitlint also fails on 13 commit bodies in #2 and 2 subject-case errors in #3
  ("UNKNOWN", "KE"); those need a squash merge or a reword, left for Watson. The local commit-msg
  check now enforces subject case, blank line and 100-char body lines like commitlint.

**Outcome:** see commits on this branch. Stacked on `task/phase0-no-demo-data` (gate tooling).

## 2026-11-26 · Claude Code (claude-opus-5-5)

**Prompt** (verbatim; secrets redacted):
> im going to give you these credentials here:
> telegram_bot_token =[REDACTED]
> telegram admin ids - we'll start with mine then hopefully we could add others later = how do i get this id,
> telegram_ops chat id - tell me how to get this as well - group is ready
> copy the nvidia api key and openrouter api keys from current hermes .env

**Decisions:**
- Wrote the bot token and the two keys from `~/.hermes/.env` into the repo's gitignored `.env`
  (mode 600, backup kept in the session scratchpad). No values printed or committed.
- `getMe` confirms the bot (@brske_bot); privacy mode is on, so in groups it only sees commands.
- Live `mkt llm-check` found: NVIDIA returns 410 for the retired `nemotron-3-super-120b-a12b`
  and 403 "Authorization failed" for current models with this key; OpenRouter works but
  Nemotron reasons by default, so a 10-token budget returned `content: null`, which llm.py
  turned into the text "None". Fixes: OpenRouter primary with `reasoning.enabled=false`
  (LLM_REASONING to opt in), NVIDIA fallback on `nemotron-3.5-super-vl-120b-a12b`, empty
  completions count as errors. Did not try the Hermes profile keys (not authorised).

**Outcome:** llm-check passes on OpenRouter (2 output tokens). Admin and ops chat IDs pending.
