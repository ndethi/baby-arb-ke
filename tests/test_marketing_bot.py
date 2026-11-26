"""Shop bot: allow-list, guarded sender, /ping and /help. No real Telegram."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
import respx
from baby_arb.config import Settings
from baby_arb.marketing.bot.app import (
    BotNotConfiguredError,
    admin_filter,
    build_application,
    help_command,
    ping,
)
from baby_arb.marketing.bot.auth import Access
from baby_arb.marketing.bot.send import API_BASE, DestinationNotAllowedError, OpsSender
from telegram import Update

ADMIN, OTHER_ADMIN, STRANGER, OPS = 111, 222, 999, -1001


def _settings(**kw):
    base = dict(
        telegram_bot_token="123:test",
        telegram_admin_ids=f"{ADMIN}, {OTHER_ADMIN}",
        telegram_ops_chat_id=OPS,
        _env_file=None,
    )
    base.update(kw)
    return Settings(**base)


def _update(user_id: int, chat_id: int, text: str = "/ping") -> Update:
    chat_type = "private" if chat_id > 0 else "supergroup"
    return Update.de_json(
        {
            "update_id": 1,
            "message": {
                "message_id": 1,
                "date": 0,
                "chat": {"id": chat_id, "type": chat_type},
                "from": {"id": user_id, "is_bot": False, "first_name": "x"},
                "text": text,
                "entities": [{"type": "bot_command", "offset": 0, "length": len(text)}],
            },
        },
        None,
    )


def test_admin_ids_parse():
    assert _settings().admin_ids == frozenset({ADMIN, OTHER_ADMIN})
    assert _settings(telegram_admin_ids="").admin_ids == frozenset()


@pytest.mark.parametrize(
    ("user", "chat", "allowed"),
    [
        (ADMIN, OPS, True),            # admin in the ops group
        (ADMIN, ADMIN, True),          # admin in their private chat
        (ADMIN, OTHER_ADMIN, True),    # chat IDs of both admins are allowed chats
        (STRANGER, OPS, False),        # someone else in the ops group
        (STRANGER, STRANGER, False),   # stranger's private chat
        (ADMIN, -5555, False),         # admin in some other group (buyers may be there)
    ],
)
def test_access_and_filter_agree(user, chat, allowed):
    access = Access.from_settings(_settings())
    assert access.allows(user, chat) is allowed
    assert bool(admin_filter(access).check_update(_update(user, chat))) is allowed


@pytest.mark.parametrize(
    "overrides",
    [{"telegram_bot_token": None}, {"telegram_admin_ids": ""}],
)
def test_bot_refuses_to_start_unconfigured(overrides):
    with pytest.raises(BotNotConfiguredError):
        build_application(_settings(**overrides))


def test_application_registers_admin_only_commands():
    app = build_application(_settings())
    commands = {c for h in app.handlers[0] for c in getattr(h, "commands", ())}
    assert {"ping", "help"} <= commands


async def test_ping_and_help_reply():
    message = MagicMock()
    message.reply_text = AsyncMock()
    update = MagicMock(effective_message=message)
    await ping(update, MagicMock())
    message.reply_text.assert_awaited_with("pong")
    await help_command(update, MagicMock())
    assert "/ping" in message.reply_text.await_args.args[0]


@respx.mock
def test_sender_refuses_non_admin_destinations_before_any_network():
    route = respx.post(f"{API_BASE}/bot123:test/sendMessage").mock(
        return_value=httpx.Response(200, json={"ok": True, "result": {"message_id": 9}})
    )
    sender = OpsSender("123:test", Access.from_settings(_settings()))
    with pytest.raises(DestinationNotAllowedError):
        sender.send_message(STRANGER, "hi")
    assert route.call_count == 0
    assert sender.send_message(OPS, "hi")["message_id"] == 9
    assert route.call_count == 1
