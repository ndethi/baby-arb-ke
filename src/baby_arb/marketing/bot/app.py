"""Build and run the shop bot (`baby-arb bot run`)."""

from __future__ import annotations

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, filters

from baby_arb.config import Settings
from baby_arb.marketing.bot.auth import Access

HELP_TEXT = (
    "babyReShop Ops bot\n"
    "/ping - check the bot is running\n"
    "/help - this list\n"
    "More commands arrive with Phase 1 (drops, previews, calendar)."
)


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


def build_application(settings: Settings) -> Application:  # type: ignore[type-arg]
    """Create the bot application with admin-only handlers.

    Raises:
        BotNotConfiguredError: TELEGRAM_BOT_TOKEN or TELEGRAM_ADMIN_IDS is empty.
    """
    if not settings.telegram_bot_token:
        raise BotNotConfiguredError("TELEGRAM_BOT_TOKEN is not set")
    access = Access.from_settings(settings)
    if not access.admin_ids:
        raise BotNotConfiguredError("TELEGRAM_ADMIN_IDS is empty; the bot would answer nobody")

    app = Application.builder().token(settings.telegram_bot_token).build()
    only_admins = admin_filter(access)
    app.add_handler(CommandHandler("ping", ping, filters=only_admins))
    app.add_handler(CommandHandler("help", help_command, filters=only_admins))
    return app
