"""Bot handlers driven with fake Telegram objects (no network)."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from baby_arb.marketing.bot import handlers as h
from baby_arb.marketing.bot.auth import Access
from baby_arb.marketing.bot.cards import Album, Text, step_messages
from baby_arb.marketing.pipeline import Blocked, Need, Preview
from baby_arb.posting.tables import Listing, ScheduleRow
from sqlmodel import Session, select

from tests.test_marketing_pipeline import CFG, PHOTO, fake_renderer, model

ADMIN, STRANGER, OPS = 111, 999, -1001


@pytest.fixture
def deps(db_engine, tmp_path):
    return h.BotDeps(engine=db_engine, load_cfg=lambda: CFG, assets_dir=tmp_path / "assets",
                     access=Access(frozenset({ADMIN}), frozenset({ADMIN, OPS})),
                     ops_chat_id=OPS, renderer=fake_renderer, completer=model(),
                     notifier_factory=None, tick_enabled=False)


class FakeBot:
    def __init__(self):
        self.messages: list[tuple[int, str, object]] = []
        self.albums: list[int] = []
        self.photos: list[int] = []

    async def send_message(self, chat_id, text, reply_markup=None):
        self.messages.append((chat_id, text, reply_markup))

    async def send_media_group(self, chat_id, media):
        self.albums.append(len(media))

    async def send_photo(self, chat_id, photo, caption=None):
        self.photos.append(chat_id)

    async def get_file(self, file_id):
        return SimpleNamespace(download_as_bytearray=AsyncMock(return_value=bytearray(PHOTO)))


def _context(deps, args=None):
    tasks: list = []
    app = SimpleNamespace(bot_data={"deps": deps},
                          create_task=lambda coro, update=None: tasks.append(coro))
    return SimpleNamespace(application=app, bot=FakeBot(), chat_data={}, args=args or [],
                           tasks=tasks)


def _msg(text=None, chat=OPS, user=ADMIN, photo=False, mgid=None, mid=1, caption=None):
    message = SimpleNamespace(
        text=text, chat_id=chat, message_id=mid, media_group_id=mgid, caption=caption,
        photo=[SimpleNamespace(file_id=f"f{mid}")] if photo else [],
        reply_text=AsyncMock(),
    )
    return SimpleNamespace(effective_message=message,
                           effective_user=SimpleNamespace(id=user), callback_query=None)


def _press(data, user=ADMIN, chat=OPS):
    query = SimpleNamespace(data=data, from_user=SimpleNamespace(id=user),
                            message=SimpleNamespace(chat=SimpleNamespace(id=chat)),
                            answer=AsyncMock())
    return SimpleNamespace(callback_query=query, effective_message=None, effective_user=None)


async def _album(ctx, n=2, caption="2000 B 0-36m washed"):
    for i in range(1, n + 1):
        await h.on_photo(_msg(photo=True, mgid="g1", mid=i, caption=caption if i == 1 else None),
                         ctx)
    assert len(ctx.tasks) == 1  # one intake per album
    await ctx.tasks.pop()


@pytest.fixture(autouse=True)
def fast_album(monkeypatch):
    monkeypatch.setattr(h, "ALBUM_WAIT_SECONDS", 0)


async def test_album_to_preview_through_buttons(deps):
    ctx = _context(deps)
    await _album(ctx, n=3)
    assert any("what is it" in m[1] for m in ctx.bot.messages)

    await h.on_text(_msg("Graco FastAction Fold stroller"), ctx)
    override = ctx.bot.messages[-1]
    assert "needs a check" in override[1] and override[2] is not None

    await h.on_button(_press("a:override:P-0001"), ctx)
    assert ctx.bot.albums == [3]
    card = ctx.bot.messages[-1]
    # The bot uses the real clock, so only the weekday and time are fixed.
    assert card[1].startswith("P-0001 · preview round 1") and "Slot: Thu" in card[1]
    assert "19:00 (drop 1/6)" in card[1]

    await h.on_button(_press("a:approve:P-0001"), ctx)
    assert "approved and queued" in ctx.bot.messages[-1][1]
    with Session(deps.engine) as s:
        assert s.get(Listing, "P-0001").status == "SCHEDULED"
        photos = sorted((deps.assets_dir / "raw" / "P-0001").iterdir())
    assert len(photos) == 3


async def test_buttons_from_strangers_are_ignored(deps):
    ctx = _context(deps)
    await _album(ctx)
    before = len(ctx.bot.messages)
    await h.on_button(_press("a:reject:P-0001", user=STRANGER), ctx)
    await h.on_button(_press("a:reject:P-0001", chat=-5555), ctx)
    assert len(ctx.bot.messages) == before
    with Session(deps.engine) as s:
        assert s.get(Listing, "P-0001").status == "INTAKE"


async def test_bad_price_answer_keeps_waiting(deps):
    ctx = _context(deps)
    await _album(ctx, caption="lovely stroller")
    assert any("what's the price" in m[1] for m in ctx.bot.messages)
    await h.on_text(_msg("cheap"), ctx)
    assert ctx.bot.messages[-1][1].startswith("⚠️ Reply with the price")
    await h.on_text(_msg("1800"), ctx)
    assert "what is it" in ctx.bot.messages[-1][1]


async def test_edit_reject_and_text_commands(deps):
    ctx = _context(deps)
    await _album(ctx)
    await h.on_text(_msg("Graco Modes stroller"), ctx)
    await h.on_button(_press("a:override:P-0001"), ctx)

    await h.on_button(_press("a:edit:P-0001"), ctx)
    await h.on_text(_msg("price bigger, use photo 2 as main"), ctx)
    assert "Applied: make price badge larger; set photo 2 as hero" in ctx.bot.messages[-1][1]

    await h.on_button(_press("a:approve:P-0001"), ctx)
    await h.on_text(_msg("move P-0001 fri 19:00"), ctx)
    assert "moved to Fri" in ctx.bot.messages[-1][1]
    await h.on_text(_msg("posted p-0001"), ctx)
    assert "It's live" in ctx.bot.messages[-1][1]
    with Session(deps.engine) as s:
        assert s.exec(select(ScheduleRow)).one().status == "POSTED"


async def test_reject_with_reason(deps):
    ctx = _context(deps)
    await _album(ctx)
    await h.on_button(_press("a:reject:P-0001"), ctx)
    await h.on_text(_msg("too worn"), ctx)
    assert "rejected" in ctx.bot.messages[-1][1] and "too worn" in ctx.bot.messages[-1][1]


async def test_post_command_marks_next_album_as_content(deps):
    ctx = _context(deps, args=["tip"])
    await h.post_command(_msg("/post tip"), ctx)
    await _album(ctx, n=1, caption="How we recall-check")
    with Session(deps.engine) as s:
        assert s.get(Listing, "C-0001").kind == "content"
    assert ctx.bot.albums == [3]  # feed, story, one TikTok frame


async def test_pause_resume_and_week(deps):
    ctx = _context(deps)
    update = _msg("/pause")
    await h.pause_command(update, ctx)
    assert "paused" in update.effective_message.reply_text.await_args.args[0]
    update = _msg("/week")
    await h.week_command(update, ctx)
    assert "slots" in update.effective_message.reply_text.await_args.args[0]


def test_step_messages_shapes(tmp_path):
    asset = tmp_path / "feed.png"
    asset.write_bytes(b"x")
    preview = Preview("P-0001", 2, [asset], "ig", "tt", "Slot: x", ["w"], ["i"], ["e"])
    outs = step_messages(preview)
    assert isinstance(outs[0], Album) and isinstance(outs[-1], Text)
    assert len(outs[-1].buttons) == 2 and outs[-1].buttons[0][0][1] == "a:approve:P-0001"
    assert step_messages(Blocked("P-0002", ["car_seat"]))[0].text.startswith("⛔ P-0002")
    need = step_messages(Need("P-0003", "override", "check"))[0]
    assert need.buttons[0][0][1] == "a:override:P-0003"


def test_application_wires_phase1_handlers():
    from baby_arb.config import Settings
    from baby_arb.marketing.bot.app import build_application

    settings = Settings(telegram_bot_token="123:t", telegram_admin_ids=str(ADMIN),
                        telegram_ops_chat_id=OPS, _env_file=None)
    app = build_application(settings, tick_enabled=False)
    commands = {c for hd in app.handlers[0] for c in getattr(hd, "commands", ())}
    assert {"ping", "help", "week", "slots", "post", "cancel", "pause", "resume"} <= commands
    assert app.bot_data["deps"].tick_enabled is False


async def test_tick_loop_starts_and_stops_with_the_app(deps, monkeypatch):
    from baby_arb.config import Settings
    from baby_arb.marketing.bot.app import build_application

    calls: list[int] = []

    async def fake_loop(app):
        calls.append(1)
        await asyncio.sleep(3600)

    monkeypatch.setattr(h, "tick_loop", fake_loop)
    deps.tick_enabled = True
    settings = Settings(telegram_bot_token="123:t", telegram_admin_ids=str(ADMIN),
                        _env_file=None)
    app = build_application(settings, deps=deps)
    await app.post_init(app)
    await asyncio.sleep(0)
    task = app.bot_data["tick_task"]
    assert calls == [1] and not task.done()
    await app.post_shutdown(app)
    assert task.cancelled()
