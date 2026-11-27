"""`baby-arb mkt cal tick`: the every-5-minutes calendar job (ENGINE_SPEC section 4).

One run:
1. Slot reminders (Phases 1-2): each QUEUED post whose slot time has come gets
   its files and captions sent to the ops chat, once (`reminded_at`).
2. MISSED: a post not marked posted within 2 hours of its reminder becomes MISSED
   and the bot asks whether to re-slot it.
3. Scheduled messages, each at most once per day (bot_state keys):
   Mon 08:00 week view · daily 18:30 tomorrow's queue · Wed 18:00 drop
   nudge (only if the drop is under half full) · Sun 16:00 review prompt.

Idempotent: running it twice never double-reminds or double-sends. Sends
nothing when there is nothing to say, and nothing at all while /pause is on.
Messages go only to the ops chat through the allow-listed sender.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Any, Protocol

from sqlmodel import Session, col, select

from baby_arb.marketing.calendar import CalendarConfig, format_week, week_view
from baby_arb.marketing.states import move_schedule
from baby_arb.posting.store import get_flag, is_paused, set_flag
from baby_arb.posting.tables import Listing, Render, ScheduleRow, as_utc

MISSED_AFTER = timedelta(hours=2)
ALBUM_LIMIT = 10


class Notifier(Protocol):
    """What tick needs from the Telegram sender (OpsSender implements it)."""

    def send_message(
        self, chat_id: int, text: str, reply_markup: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Send text."""
        ...

    def send_media_group(
        self, chat_id: int, paths: Sequence[Path], caption: str | None = None
    ) -> list[dict[str, Any]]:
        """Send an album."""
        ...


@dataclass(frozen=True)
class Digest:
    """A scheduled message: weekday (None = daily), local time and builder name."""

    key: str
    weekday: int | None
    at: time


DIGESTS = (
    Digest("monday_week", 0, time(8, 0)),
    Digest("daily_tomorrow", None, time(18, 30)),
    Digest("wednesday_drop", 2, time(18, 0)),
    Digest("sunday_review", 6, time(16, 0)),
)


def buttons(*rows: list[tuple[str, str]]) -> dict[str, Any]:
    """Inline keyboard markup from rows of (label, callback_data)."""
    return {"inline_keyboard": [[{"text": t, "callback_data": d} for t, d in row]
                                for row in rows]}


def _assets(session: Session, listing: Listing) -> list[Path]:
    rows = session.exec(
        select(Render).where(Render.listing_code == listing.code, Render.round == listing.round)
        .order_by(col(Render.id))
    ).all()
    return [Path(r.path) for r in rows if Path(r.path).is_file()][:ALBUM_LIMIT]


def _remind(session: Session, cfg: CalendarConfig, notifier: Notifier, chat: int,
            row: ScheduleRow, now: datetime) -> str:
    listing = session.get(Listing, row.listing_code)
    if listing is None:  # pragma: no cover - FK guarantees it
        return f"{row.listing_code}: listing missing"
    local = as_utc(row.slot_at).astimezone(cfg.tz)
    assets = _assets(session, listing)
    if assets:
        notifier.send_media_group(chat, assets, caption=f"{listing.code} · files to post")
    if listing.caption_ig:
        notifier.send_message(chat, f"IG + FB caption ({listing.code}):\n\n{listing.caption_ig}")
    if listing.caption_tiktok:
        notifier.send_message(chat, f"TikTok caption ({listing.code}):\n\n{listing.caption_tiktok}")
    notifier.send_message(
        chat,
        f"⏰ Time to post {listing.code} ({row.kind}, {local:%a %H:%M}).\n"
        "IG + FB: feed graphic in Business Suite, story to Stories. "
        "TikTok: the frames as a photo post, sound from TikTok's library.\n"
        f"Then tap Posted or reply 'posted {listing.code}'.",
        reply_markup=buttons([("✅ Posted", f"a:posted:{listing.code}")]),
    )
    row.reminded_at = now
    session.add(row)
    session.commit()
    return f"reminded {listing.code}"


def _miss(session: Session, notifier: Notifier, chat: int, row: ScheduleRow) -> str:
    move_schedule(session, row, "MISSED", "system", "not marked posted within 2 h")
    session.commit()
    notifier.send_message(
        chat,
        f"⌛ {row.listing_code} wasn't marked posted. Re-slot it to the next free "
        f"{row.kind} slot, or skip?",
        reply_markup=buttons([("🕒 Re-slot", f"a:reslot:{row.listing_code}"),
                              ("⏭ Skip", f"a:skip:{row.listing_code}"),
                              ("✅ It was posted", f"a:posted:{row.listing_code}")]),
    )
    return f"missed {row.listing_code}"


def _rows_on(session: Session, cfg: CalendarConfig, day: datetime) -> list[ScheduleRow]:
    start = datetime.combine(day.date(), time.min, tzinfo=cfg.tz)
    end = start + timedelta(days=1)
    return list(session.exec(
        select(ScheduleRow).where(
            col(ScheduleRow.status).in_(("PROPOSED", "QUEUED")),
            ScheduleRow.slot_at >= start, ScheduleRow.slot_at < end,
        ).order_by(col(ScheduleRow.slot_at))
    ).all())


def build_digest(key: str, session: Session, cfg: CalendarConfig, now: datetime) -> str | None:
    """Text for a scheduled message, or None when there is nothing to say."""
    local = now.astimezone(cfg.tz)
    if key == "monday_week":
        statuses = week_view(session, cfg, local.date())
        return format_week(statuses) if statuses else None
    if key == "daily_tomorrow":
        tomorrow = local + timedelta(days=1)
        rows = _rows_on(session, cfg, tomorrow)
        slots = [s for s in week_view(session, cfg, tomorrow.date())
                 if s.slot.at.date() == tomorrow.date()]
        if not rows and not slots:
            return None
        lines = [f"Tomorrow ({tomorrow:%a %d %b}):"]
        for r in rows:
            at = as_utc(r.slot_at).astimezone(cfg.tz)
            state = "approved" if r.status == "QUEUED" else "awaiting approval"
            lines.append(f"• {at:%H:%M} {r.kind}: {r.listing_code} ({state})")
        for s in slots:
            if s.slot.free:
                lines.append(f"• {s.slot.at:%H:%M} {s.slot.kind}: {s.slot.free} of "
                             f"{s.slot.max} places empty")
        lines.append("Change anything tonight with move / skip.")
        return "\n".join(lines)
    if key == "wednesday_drop":
        drop_day = (local + timedelta(days=1)).date()
        drops = [s for s in week_view(session, cfg, drop_day)
                 if s.slot.kind == "drop" and s.slot.at.date() == drop_day]
        if not drops:
            return None
        slot = drops[0].slot
        if slot.filled * 2 >= slot.max:
            return None
        return (f"Drop tomorrow ({slot.at:%a %H:%M}): {slot.free} of {slot.max} slots still "
                "empty. Send photos to fill it.")
    if key == "sunday_review":
        return ("Sunday review: how did the week go? Note what sold, what didn't and any "
                "edits you kept repeating. /week shows next week's slots.")
    raise ValueError(f"unknown digest {key}")  # pragma: no cover


def _digests(session: Session, cfg: CalendarConfig, notifier: Notifier, chat: int,
             now: datetime) -> list[str]:
    local = now.astimezone(cfg.tz)
    done: list[str] = []
    for digest in DIGESTS:
        if digest.weekday is not None and local.weekday() != digest.weekday:
            continue
        if local.time() < digest.at:
            continue
        flag = f"sent:{digest.key}:{local.date().isoformat()}"
        if get_flag(session, flag):
            continue
        text = build_digest(digest.key, session, cfg, now)
        set_flag(session, flag, "1" if text else "0")
        session.commit()
        if text:
            notifier.send_message(chat, text)
            done.append(f"sent {digest.key}")
    return done


def tick(session: Session, cfg: CalendarConfig, notifier: Notifier, ops_chat_id: int,
         now: datetime) -> list[str]:
    """Run one calendar tick. Returns what happened (empty when nothing did)."""
    if is_paused(session):
        return []
    done: list[str] = []
    due = session.exec(
        select(ScheduleRow).where(
            ScheduleRow.status == "QUEUED",
            col(ScheduleRow.reminded_at).is_(None),
            ScheduleRow.slot_at <= now,
        ).order_by(col(ScheduleRow.slot_at))
    ).all()
    for row in due:
        done.append(_remind(session, cfg, notifier, ops_chat_id, row, now))
    late = session.exec(
        select(ScheduleRow).where(
            ScheduleRow.status == "QUEUED",
            col(ScheduleRow.reminded_at).is_not(None),
            col(ScheduleRow.reminded_at) <= now - MISSED_AFTER,
        )
    ).all()
    for row in late:
        done.append(_miss(session, notifier, ops_chat_id, row))
    done += _digests(session, cfg, notifier, ops_chat_id, now)
    return done
