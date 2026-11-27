"""Build and run the shop bot (`baby-arb bot run`)."""

from __future__ import annotations

import asyncio
import contextlib
from functools import partial
from pathlib import Path

from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from baby_arb.config import Settings
from baby_arb.marketing.bot import handlers as h
from baby_arb.marketing.bot.auth import Access
from baby_arb.marketing.bot.cards import HELP
from baby_arb.marketing.bot.send import OpsSender
from baby_arb.marketing.calendar import load_config
from baby_arb.marketing.llm import complete
from baby_arb.marketing.lookup import make_lookup
from baby_arb.marketing.render.static import render_listing
from baby_arb.storage.db import get_engine

HELP_TEXT = HELP


class BotNotConfiguredError(RuntimeError):
    """Raised when the token or admin allow-list is missing."""


async def ping(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reply "pong" so admins can check the bot is alive."""
    if update.effective_message is not None:
        await update.effective_message.reply_text("pong")


async def help_command(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    """List available commands."""
    if update.effective_message is not None:
        await update.effective_message.reply_text(HELP_TEXT)


def admin_filter(access: Access) -> filters.BaseFilter:
    """Messages from an allow-listed admin in an allow-listed chat."""
    return filters.User(user_id=access.admin_ids) & filters.Chat(chat_id=access.chat_ids)


def make_deps(settings: Settings, access: Access, tick_enabled: bool = True) -> h.BotDeps:
    """Real dependencies from settings."""
    token = settings.telegram_bot_token or ""
    engine = get_engine(settings.database_url)
    return h.BotDeps(
        engine=engine,
        load_cfg=load_config,
        assets_dir=Path(settings.marketing_assets_dir),
        access=access,
        ops_chat_id=settings.telegram_ops_chat_id,
        renderer=partial(render_listing, channel=settings.render_browser_channel),
        completer=complete,
        notifier_factory=lambda: OpsSender(token, access),
        lookup=make_lookup(settings.brave_search_api_key, engine, settings.brave_daily_call_cap),
        tick_enabled=tick_enabled,
    )


def build_application(
    settings: Settings, deps: h.BotDeps | None = None, tick_enabled: bool = True
) -> Application:  # type: ignore[type-arg]
    """Create the bot application with admin-only handlers.

    Raises:
        BotNotConfiguredError: TELEGRAM_BOT_TOKEN or TELEGRAM_ADMIN_IDS is empty.
    """
    if not settings.telegram_bot_token:
        raise BotNotConfiguredError("TELEGRAM_BOT_TOKEN is not set")
    access = Access.from_settings(settings)
    if not access.admin_ids:
        raise BotNotConfiguredError("TELEGRAM_ADMIN_IDS is empty; the bot would answer nobody")

    async def post_init(app: Application) -> None:  # type: ignore[type-arg]
        # The app is not "running" yet here, so own the task and cancel it on shutdown.
        if app.bot_data["deps"].tick_enabled:
            app.bot_data["tick_task"] = asyncio.get_running_loop().create_task(h.tick_loop(app))

    async def post_shutdown(app: Application) -> None:  # type: ignore[type-arg]
        task = app.bot_data.get("tick_task")
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    app = (
        Application.builder()
        .token(settings.telegram_bot_token)
        # Preview albums are several images; the 5-20 s defaults timed out.
        .read_timeout(60)
        .write_timeout(60)
        .media_write_timeout(120)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )
    app.bot_data["deps"] = deps or make_deps(settings, access, tick_enabled)
    only_admins = admin_filter(access)
    app.add_handler(CommandHandler("ping", ping, filters=only_admins))
    app.add_handler(CommandHandler("help", help_command, filters=only_admins))
    app.add_handler(CommandHandler("week", h.week_command, filters=only_admins))
    app.add_handler(CommandHandler("slots", h.slots_command, filters=only_admins))
    app.add_handler(CommandHandler("post", h.post_command, filters=only_admins))
    app.add_handler(CommandHandler("cancel", h.cancel_command, filters=only_admins))
    app.add_handler(CommandHandler(["pause", "resume"], h.pause_command, filters=only_admins))
    app.add_handler(MessageHandler(only_admins & filters.PHOTO, h.on_photo))
    app.add_handler(MessageHandler(only_admins & filters.TEXT & ~filters.COMMAND, h.on_text))
    app.add_handler(CallbackQueryHandler(h.on_button, pattern=r"^a:"))
    app.add_error_handler(h.on_error)
    return app
