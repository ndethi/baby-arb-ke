"""Thin Telegram bot for the shop (python-telegram-bot).

Why a separate process and not a Hermes skill: docs/marketing/ENGINE_SPEC.md
section 3 (Phase 0 decision) and the PR description. Hermes runs the
scheduled `baby-arb mkt ...` commands as no-agent cron jobs.
"""
