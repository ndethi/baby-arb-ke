"""Telegram handlers for the Phase 1 flow. Thin: every decision lives in pipeline.py.

- Only allow-listed admins in allow-listed chats are heard (handler filters
  for messages, an explicit check for button presses).
- Pipeline work (database, model calls, Playwright) runs in a worker thread.
- Pending questions ("what's the price?", "what should change?") are kept in
  bot_state per chat and admin, so they survive a restart.
- The bot runs `cal tick` every 5 minutes itself (and right after ⏩ Now);
  tick is idempotent, so a Hermes cron running it as well is harmless.
"""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeVar

import structlog
from sqlalchemy.engine import Engine
from sqlmodel import Session
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, Update
from telegram.ext import Application, ContextTypes

from baby_arb.marketing import pipeline as pl
from baby_arb.marketing.bot.auth import Access
from baby_arb.marketing.bot.cards import HELP, Album, Out, Text, step_messages
from baby_arb.marketing.calendar import CONTENT_KINDS, CalendarConfig, format_week, week_view
from baby_arb.marketing.render.static import RenderError
from baby_arb.marketing.tick import Notifier, tick
from baby_arb.posting.store import get_flag, set_flag
from baby_arb.posting.tables import utcnow

logger = structlog.get_logger()

T = TypeVar("T")

ALBUM_WAIT_SECONDS = 2.0
TICK_SECONDS = 300
CODE = r"([PLC]-\d{4})"
_MOVE = re.compile(rf"^move\s+{CODE}\s+(.+)$", re.IGNORECASE)
_SIMPLE = re.compile(rf"^(skip|posted|test)\s+{CODE}$", re.IGNORECASE)
_SIMPLE_STEPS: dict[str, Callable[[pl.Context, str], str]] = {
    "skip": pl.skip, "posted": pl.posted, "test": pl.mark_test,
}


@dataclass
class BotDeps:
    """Everything the handlers need (tests pass fakes)."""

    engine: Engine
    load_cfg: Callable[[], CalendarConfig]
    assets_dir: Path
    access: Access
    ops_chat_id: int | None
    renderer: pl.Renderer
    completer: pl.Completer
    notifier_factory: Callable[[], Notifier] | None = None
    tick_enabled: bool = True


def deps_of(context: ContextTypes.DEFAULT_TYPE) -> BotDeps:
    """The BotDeps stored on the application."""
    deps: BotDeps = context.application.bot_data["deps"]
    return deps


# --------------------------------------------------------------------------- state

def _await_key(chat_id: int, user_id: int) -> str:
    return f"await:{chat_id}:{user_id}"


def _set_await(deps: BotDeps, chat_id: int, user_id: int, what: str | None,
               code: str | None = None) -> None:
    with Session(deps.engine) as session:
        set_flag(session, _await_key(chat_id, user_id),
                 json.dumps({"what": what, "code": code}) if what else "")
        session.commit()


def _get_await(deps: BotDeps, chat_id: int, user_id: int) -> dict[str, Any] | None:
    with Session(deps.engine) as session:
        raw = get_flag(session, _await_key(chat_id, user_id))
    if not raw:
        return None
    data: dict[str, Any] = json.loads(raw)
    return data


# --------------------------------------------------------------------------- running

def _in_session(deps: BotDeps, actor: str, fn: Callable[[pl.Context], T]) -> T:
    with Session(deps.engine) as session:
        ctx = pl.Context(session=session, cfg=deps.load_cfg(), assets_dir=deps.assets_dir,
                         actor=actor, now=utcnow(), renderer=deps.renderer,
                         completer=deps.completer)
        return fn(ctx)


async def run_flow(deps: BotDeps, actor: str, fn: Callable[[pl.Context], T]) -> T | Text:
    """Run a pipeline step in a worker thread; FlowError becomes a message."""
    try:
        return await asyncio.to_thread(_in_session, deps, actor, fn)
    except pl.FlowError as exc:
        return Text(f"⚠️ {exc}")
    except RenderError as exc:
        logger.error("render failed", error=str(exc))
        return Text(f"⚠️ Rendering failed: {exc}")


async def send_outs(context: ContextTypes.DEFAULT_TYPE, chat_id: int, outs: list[Out]) -> None:
    """Send pipeline output to the chat the admin wrote from."""
    for out in outs:
        if isinstance(out, Album):
            if len(out.paths) == 1:
                await context.bot.send_photo(chat_id, out.paths[0].read_bytes(),
                                             caption=out.caption)
                continue
            media = [InputMediaPhoto(p.read_bytes(), caption=out.caption if i == 0 else None)
                     for i, p in enumerate(out.paths)]
            await context.bot.send_media_group(chat_id, media)
        else:
            markup = None
            if out.buttons:
                markup = InlineKeyboardMarkup(
                    [[InlineKeyboardButton(t, callback_data=d) for t, d in row]
                     for row in out.buttons]
                )
            await context.bot.send_message(chat_id, out.text, reply_markup=markup)


async def _respond(context: ContextTypes.DEFAULT_TYPE, deps: BotDeps, chat_id: int,
                   user_id: int, result: object) -> None:
    """Send a step (or text) and remember what the bot is now waiting for."""
    if isinstance(result, Text):
        await send_outs(context, chat_id, [result])
        return
    if isinstance(result, str):
        await send_outs(context, chat_id, [Text(result)])
        return
    if isinstance(result, pl.Need) and result.what in {"price", "title"}:
        _set_await(deps, chat_id, user_id, result.what, result.code)
    elif isinstance(result, pl.Question):
        _set_await(deps, chat_id, user_id, "edit", result.code)
    else:
        _set_await(deps, chat_id, user_id, None)
    if isinstance(result, pl.Need | pl.Blocked | pl.Preview | pl.Question):
        await send_outs(context, chat_id, step_messages(result))


# --------------------------------------------------------------------------- photos

async def on_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Collect an album (photos sharing media_group_id), then run intake once."""
    msg, user = update.effective_message, update.effective_user
    if msg is None or user is None or not msg.photo:
        return
    deps = deps_of(context)
    key = msg.media_group_id or f"single:{msg.message_id}"
    albums: dict[str, dict[str, Any]] = context.chat_data.setdefault("albums", {})  # type: ignore[union-attr]
    entry = albums.setdefault(key, {"photos": [], "caption": None, "started": False})
    entry["photos"].append((msg.message_id, msg.photo[-1].file_id))
    if msg.caption:
        entry["caption"] = msg.caption
    if entry["started"]:
        return
    entry["started"] = True
    # Updates are handled one at a time, so wait for the rest of the album in a task.
    context.application.create_task(
        _finish_album(context, deps, msg.chat_id, user.id, key), update=update
    )


async def _finish_album(context: ContextTypes.DEFAULT_TYPE, deps: BotDeps, chat_id: int,
                        user_id: int, key: str) -> None:
    await asyncio.sleep(ALBUM_WAIT_SECONDS)
    albums: dict[str, dict[str, Any]] = context.chat_data.setdefault("albums", {})  # type: ignore[union-attr]
    entry = albums.pop(key, None)
    if entry is None:
        return
    photos = []
    for _mid, file_id in sorted(entry["photos"]):
        tg_file = await context.bot.get_file(file_id)
        photos.append(bytes(await tg_file.download_as_bytearray()))

    caption: str = (entry["caption"] or "").strip()
    content_kind: str | None = None
    post = re.match(r"^/post(?:@\w+)?\s+(\w+)\s*(.*)$", caption, re.IGNORECASE | re.DOTALL)
    if post:
        content_kind, caption = post.group(1).lower(), post.group(2)
    else:
        pending = _get_await(deps, chat_id, user_id)
        if pending and pending.get("what") == "post":
            content_kind = pending.get("code")
    if content_kind is not None and content_kind not in CONTENT_KINDS:
        await send_outs(context, chat_id, [Text(f"⚠️ /post needs one of: "
                                                f"{', '.join(CONTENT_KINDS)}.")])
        return
    await context.bot.send_message(chat_id, f"Got {len(photos)} photo(s). Working on it…")
    result = await run_flow(deps, str(user_id),
                            lambda ctx: pl.intake(ctx, photos, caption, content_kind))
    await _respond(context, deps, chat_id, user_id, result)


# --------------------------------------------------------------------------- text

async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Text commands (move/skip/posted) and answers to pending questions."""
    msg, user = update.effective_message, update.effective_user
    if msg is None or user is None or not msg.text:
        return
    deps = deps_of(context)
    text = msg.text.strip()
    actor, chat_id = str(user.id), msg.chat_id

    if m := _MOVE.match(text):
        code, when = m.group(1).upper(), m.group(2)
        result: object = await run_flow(deps, actor, lambda ctx: pl.move(ctx, code, when))
        await _respond(context, deps, chat_id, user.id, result)
        return
    if m := _SIMPLE.match(text):
        verb, code = m.group(1).lower(), m.group(2).upper()
        fn = _SIMPLE_STEPS[verb]
        result = await run_flow(deps, actor, lambda ctx: fn(ctx, code))
        await _respond(context, deps, chat_id, user.id, result)
        return

    pending = _get_await(deps, chat_id, user.id)
    if not pending or not pending.get("what"):
        return
    what, code = pending["what"], pending.get("code") or ""
    if what in {"price", "title"}:
        result = await run_flow(deps, actor, lambda ctx: pl.answer(ctx, code, what, text))
    elif what == "edit":
        await context.bot.send_message(chat_id, f"Editing {code}…")
        result = await run_flow(deps, actor, lambda ctx: pl.edit(ctx, code, text))
    elif what == "reject":
        _set_await(deps, chat_id, user.id, None)
        result = await run_flow(deps, actor, lambda ctx: pl.reject(ctx, code, text))
    elif what == "move":
        _set_await(deps, chat_id, user.id, None)
        result = await run_flow(deps, actor, lambda ctx: pl.move(ctx, code, text))
    else:
        return
    if isinstance(result, Text) and what in {"price", "title", "edit"}:
        await send_outs(context, chat_id, [result])  # keep waiting for a usable answer
        return
    await _respond(context, deps, chat_id, user.id, result)


# --------------------------------------------------------------------------- buttons

async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Preview, review and reminder buttons. Ignores anyone not allow-listed."""
    query = update.callback_query
    if query is None or query.message is None or query.data is None:
        return
    deps = deps_of(context)
    chat_id = query.message.chat.id
    if not deps.access.allows(query.from_user.id, chat_id):
        await query.answer()
        return
    await query.answer()
    parts = query.data.split(":", 2)
    if len(parts) != 3 or parts[0] != "a":
        return
    action, code = parts[1], parts[2]
    actor, uid = str(query.from_user.id), query.from_user.id
    result: object
    if action == "approve":
        result = await run_flow(deps, actor, lambda ctx: pl.approve(ctx, code))
    elif action == "now":
        result = await run_flow(deps, actor, lambda ctx: pl.approve(ctx, code, now=True))
        await _respond(context, deps, chat_id, uid, result)
        await run_tick(deps)
        return
    elif action == "edit":
        _set_await(deps, chat_id, uid, "edit", code)
        result = Text(f"{code}: what should change? e.g. \"price bigger, drop 'washed', "
                      "use photo 3 as main\"")
    elif action == "reject":
        _set_await(deps, chat_id, uid, "reject", code)
        result = Text(f"{code}: reason for rejecting (one line, optional)?",
                      [[("No reason", f"a:rejectx:{code}")]])
    elif action == "rejectx":
        _set_await(deps, chat_id, uid, None)
        result = await run_flow(deps, actor, lambda ctx: pl.reject(ctx, code, None))
    elif action == "move":
        _set_await(deps, chat_id, uid, "move", code)
        result = Text(f"{code}: when? e.g. 'fri 19:00', 'tomorrow 12:30', '2026-12-01 19:00'")
    elif action == "skip":
        result = await run_flow(deps, actor, lambda ctx: pl.skip(ctx, code))
    elif action == "override":
        result = await run_flow(deps, actor, lambda ctx: pl.override(ctx, code))
    elif action == "posted":
        result = await run_flow(deps, actor, lambda ctx: pl.posted(ctx, code))
    elif action == "reslot":
        result = await run_flow(deps, actor, lambda ctx: pl.reslot(ctx, code))
    else:
        return
    await _respond(context, deps, chat_id, uid, result)


# --------------------------------------------------------------------------- commands

async def help_command(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    """List commands."""
    if update.effective_message is not None:
        await update.effective_message.reply_text(HELP)


async def week_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/week: this week's slots (filled, empty, capacity)."""
    if update.effective_message is None:
        return
    deps = deps_of(context)

    def build() -> str:
        cfg = deps.load_cfg()
        with Session(deps.engine) as session:
            return format_week(week_view(session, cfg, utcnow().astimezone(cfg.tz).date()))

    await update.effective_message.reply_text(await asyncio.to_thread(build))


async def slots_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/slots: the calendar rhythm (edited only in config/calendar.yaml)."""
    if update.effective_message is None:
        return
    cfg = deps_of(context).load_cfg()
    lines = ["Calendar (config/calendar.yaml):"]
    for kind, spec in cfg.slots.items():
        lines.append(f"• {kind}: {', '.join(spec.days)} {spec.time}, max {spec.max}")
    lines.append(f"Blackout: {', '.join(cfg.blackout_days) or 'none'} · min gap "
                 f"{cfg.min_gap_minutes} min")
    for s in cfg.specials:
        lines.append(f"• special {s.date:%a %d %b} {s.kind} {s.time}"
                     + (f": {s.label}" if s.label else ""))
    await update.effective_message.reply_text("\n".join(lines))


async def post_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/post teaser|tip|behind: the next album becomes a content post."""
    msg, user = update.effective_message, update.effective_user
    if msg is None or user is None:
        return
    kind = (context.args or [""])[0].lower()
    if kind not in CONTENT_KINDS:
        await msg.reply_text(f"Use /post {'|'.join(CONTENT_KINDS)}, then send the album.")
        return
    _set_await(deps_of(context), msg.chat_id, user.id, "post", kind)
    await msg.reply_text(f"OK: send the {kind} photos as one album with a one-line caption.")


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/cancel: forget the pending question."""
    msg, user = update.effective_message, update.effective_user
    if msg is None or user is None:
        return
    _set_await(deps_of(context), msg.chat_id, user.id, None)
    await msg.reply_text("Cancelled.")


async def pause_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/pause and /resume: stop or start scheduled messages."""
    msg = update.effective_message
    if msg is None or msg.text is None:
        return
    paused = msg.text.lstrip("/").lower().startswith("pause")
    with Session(deps_of(context).engine) as session:
        set_flag(session, "paused", "1" if paused else "0")
        session.commit()
    await msg.reply_text("⏸ Scheduled messages paused. /resume to restart." if paused
                         else "▶️ Scheduled messages resumed.")


# --------------------------------------------------------------------------- tick

def _tick_once(deps: BotDeps) -> list[str]:
    if deps.ops_chat_id is None or deps.notifier_factory is None:
        return []
    cfg = deps.load_cfg()
    with Session(deps.engine) as session:
        return tick(session, cfg, deps.notifier_factory(), deps.ops_chat_id, utcnow())


async def run_tick(deps: BotDeps) -> list[str]:
    """One calendar tick in a worker thread; errors are logged, never raised."""
    try:
        return await asyncio.to_thread(_tick_once, deps)
    except Exception as exc:  # a failed tick must not stop the bot
        logger.error("tick failed", error=str(exc))
        return []


async def tick_loop(app: Application) -> None:  # type: ignore[type-arg]
    """Run cal tick every 5 minutes while the bot is up."""
    deps: BotDeps = app.bot_data["deps"]
    while True:
        done = await run_tick(deps)
        if done:
            logger.info("tick", done=done)
        await asyncio.sleep(TICK_SECONDS)
