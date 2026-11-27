"""The content calendar (ENGINE_SPEC section 4). Deterministic: no model calls.

`config/calendar.yaml` is the calendar. A slot is one (kind, local time) on a
day of the weekly rhythm, or a dated special. A slot holds up to `max` posts
(a batch, shown as "listing 2/4"). `min_gap_minutes` keeps two *different*
occupied slot times on the same channel apart.

All stored times are UTC; Nairobi has no DST, so local arithmetic is safe.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

import yaml
from pydantic import BaseModel, Field, field_validator
from sqlmodel import Session, col, select

from baby_arb.posting.tables import ScheduleRow, as_utc

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PATH = REPO_ROOT / "config" / "calendar.yaml"

Weekday = Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
WEEKDAYS: tuple[Weekday, ...] = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

# Schedule rows that take a place in a slot.
OCCUPYING = ("PROPOSED", "QUEUED", "POSTED")

CONTENT_KINDS = ("teaser", "tip", "behind")


class SlotSpec(BaseModel):
    """One recurring slot kind."""

    days: list[Weekday]
    time: str
    max: int = Field(ge=1)

    @field_validator("time")
    @classmethod
    def _hhmm(cls, value: str) -> str:
        parse_hhmm(value)
        return value


class Special(BaseModel):
    """A one-off dated slot; replaces that kind's regular slot on the date."""

    date: date
    kind: str
    time: str
    label: str | None = None

    @field_validator("time")
    @classmethod
    def _hhmm(cls, value: str) -> str:
        parse_hhmm(value)
        return value


class CalendarConfig(BaseModel):
    """Validated `config/calendar.yaml`."""

    timezone: str = "Africa/Nairobi"
    channels: list[str]
    slots: dict[str, SlotSpec]
    blackout_days: list[Weekday] = []
    min_gap_minutes: int = Field(default=90, ge=0)
    lookahead_days: int = Field(default=14, ge=1)
    specials: list[Special] = []

    @property
    def tz(self) -> ZoneInfo:
        """The calendar's time zone."""
        return ZoneInfo(self.timezone)

    def spec(self, kind: str) -> SlotSpec:
        """The slot spec for `kind`.

        Raises:
            KeyError: unknown kind.
        """
        if kind not in self.slots:
            raise KeyError(f"unknown slot kind {kind!r}; known: {', '.join(self.slots)}")
        return self.slots[kind]


@dataclass(frozen=True)
class Slot:
    """A concrete slot instance."""

    kind: str
    at: datetime  # aware, calendar time zone
    max: int
    filled: int = 0
    label: str | None = None

    @property
    def free(self) -> int:
        """Places left in the slot (never negative)."""
        return max(self.max - self.filled, 0)


def parse_hhmm(value: str) -> time:
    """Parse "HH:MM" (24 h).

    Raises:
        ValueError: not a valid time.
    """
    match = re.fullmatch(r"([01]?\d|2[0-3]):([0-5]\d)", value.strip())
    if not match:
        raise ValueError(f"time must be HH:MM, got {value!r}")
    return time(int(match.group(1)), int(match.group(2)))


def load_config(path: Path | None = None) -> CalendarConfig:
    """Load and validate the calendar file."""
    raw = yaml.safe_load((path or DEFAULT_PATH).read_text(encoding="utf-8"))
    return CalendarConfig.model_validate(raw)


def slot_kind_for(code: str, content_kind: str | None = None) -> str:
    """P-code -> drop, L-code -> listing, C-code -> its content kind.

    Raises:
        ValueError: C-code without a valid content kind, or unknown prefix.
    """
    prefix = code.split("-", 1)[0]
    if prefix == "P":
        return "drop"
    if prefix == "L":
        return "listing"
    if prefix == "C":
        if content_kind not in CONTENT_KINDS:
            raise ValueError(f"content post {code} needs a kind: {', '.join(CONTENT_KINDS)}")
        return content_kind
    raise ValueError(f"unknown listing code {code!r}")


def slots_between(cfg: CalendarConfig, kind: str, start: date, end: date) -> list[Slot]:
    """Every slot of `kind` on dates start..end inclusive, in time order.

    A special for `kind` on a date replaces the regular slot that day and
    also counts on a day that is off-rhythm or blacked out.
    """
    spec = cfg.spec(kind)
    tz = cfg.tz
    specials = {s.date: s for s in cfg.specials if s.kind == kind}
    out: list[Slot] = []
    day = start
    while day <= end:
        weekday = WEEKDAYS[day.weekday()]
        special = specials.get(day)
        if special is not None:
            at = datetime.combine(day, parse_hhmm(special.time), tzinfo=tz)
            out.append(Slot(kind, at, spec.max, label=special.label))
        elif weekday in spec.days and weekday not in cfg.blackout_days:
            at = datetime.combine(day, parse_hhmm(spec.time), tzinfo=tz)
            out.append(Slot(kind, at, spec.max))
        day += timedelta(days=1)
    return out


def _occupied(session: Session, start: datetime, end: datetime) -> list[ScheduleRow]:
    rows = session.exec(
        select(ScheduleRow).where(
            col(ScheduleRow.status).in_(OCCUPYING),
            ScheduleRow.slot_at >= start - timedelta(days=1),
            ScheduleRow.slot_at <= end + timedelta(days=1),
        )
    ).all()
    return list(rows)


def _channels(row: ScheduleRow) -> set[str]:
    return {c for c in row.channels.split(",") if c}


def _fill(slot: Slot, rows: Iterable[ScheduleRow]) -> Slot:
    at_utc = as_utc(slot.at)
    filled = sum(1 for r in rows if r.kind == slot.kind and as_utc(r.slot_at) == at_utc)
    return Slot(slot.kind, slot.at, slot.max, filled, slot.label)


def gap_conflict(
    cfg: CalendarConfig,
    at: datetime,
    channels: set[str],
    rows: Iterable[ScheduleRow],
    exclude_id: int | None = None,
) -> ScheduleRow | None:
    """An occupied row at a different time within min_gap on a shared channel."""
    gap = timedelta(minutes=cfg.min_gap_minutes)
    at_utc = as_utc(at)
    for row in rows:
        if row.id is not None and row.id == exclude_id:
            continue
        other = as_utc(row.slot_at)
        if other != at_utc and abs(other - at_utc) < gap and channels & _channels(row):
            return row
    return None


def next_free_slot(
    session: Session,
    cfg: CalendarConfig,
    kind: str,
    after: datetime,
    channels: Iterable[str] | None = None,
) -> Slot | None:
    """The earliest slot of `kind` after `after` with room and no gap clash.

    Looks `lookahead_days` ahead. A full slot rolls to the next day of that
    kind, a full week to the next week. Slots at or before `after` are
    skipped. Returns None when nothing fits; the caller asks the admin.
    """
    tz = cfg.tz
    local_after = after.astimezone(tz)
    end = local_after.date() + timedelta(days=cfg.lookahead_days)
    wanted = set(channels or cfg.channels)
    candidates = slots_between(cfg, kind, local_after.date(), end)
    if not candidates:
        return None
    rows = _occupied(session, candidates[0].at, candidates[-1].at)
    for slot in candidates:
        if slot.at <= local_after:
            continue
        filled = _fill(slot, rows)
        if filled.free == 0:
            continue
        if gap_conflict(cfg, slot.at, wanted, rows) is not None:
            continue
        return filled
    return None


@dataclass(frozen=True)
class SlotStatus:
    """One slot in a week view."""

    slot: Slot
    codes: list[str]

    @property
    def empty(self) -> bool:
        """No posts in this slot yet."""
        return not self.codes


def week_start(day: date) -> date:
    """The Monday of `day`'s week."""
    return day - timedelta(days=day.weekday())


def week_view(session: Session, cfg: CalendarConfig, start: date) -> list[SlotStatus]:
    """Every slot of every kind in the Monday-Sunday week holding `start`."""
    monday = week_start(start)
    sunday = monday + timedelta(days=6)
    slots = sorted(
        (s for kind in cfg.slots for s in slots_between(cfg, kind, monday, sunday)),
        key=lambda s: (s.at, s.kind),
    )
    if not slots:
        return []
    rows = _occupied(session, slots[0].at, slots[-1].at)
    out: list[SlotStatus] = []
    for slot in slots:
        at_utc = as_utc(slot.at)
        codes = sorted(
            r.listing_code for r in rows if r.kind == slot.kind and as_utc(r.slot_at) == at_utc
        )
        out.append(SlotStatus(Slot(slot.kind, slot.at, slot.max, len(codes), slot.label), codes))
    return out


def format_slot_line(slot: Slot, position: int | None = None) -> str:
    """E.g. "Slot: Fri 27 Nov, 12:30 (listing 2/4)"."""
    pos = position if position is not None else slot.filled + 1
    label = f" · {slot.label}" if slot.label else ""
    return f"Slot: {slot.at:%a %d %b, %H:%M} ({slot.kind} {pos}/{slot.max}){label}"


def format_week(statuses: list[SlotStatus], title: str = "This week's slots") -> str:
    """Plain-text week view for the Monday message and /week."""
    if not statuses:
        return f"{title}: no slots configured."
    lines = [f"{title}:"]
    for st in statuses:
        s = st.slot
        mark = "⬜" if st.empty else ("✅" if s.free == 0 else "🟨")
        codes = ", ".join(st.codes) if st.codes else "empty"
        label = f" · {s.label}" if s.label else ""
        lines.append(f"{mark} {s.at:%a %d %b %H:%M} {s.kind} {s.filled}/{s.max}: {codes}{label}")
    needs = [st for st in statuses if st.slot.free > 0]
    if needs:
        kinds = sorted({st.slot.kind for st in needs})
        lines.append(f"Needs stock: {', '.join(kinds)}")
    return "\n".join(lines)


_WHEN = re.compile(
    r"^(?:(?P<day>mon|tue|wed|thu|fri|sat|sun|today|tomorrow|\d{4}-\d{2}-\d{2})\s+)?"
    r"(?P<time>\d{1,2}:\d{2})$",
    re.IGNORECASE,
)


def parse_when(text: str, now: datetime, cfg: CalendarConfig) -> datetime:
    """Parse "fri 19:00", "tomorrow 12:30", "2026-12-01 19:00" or "18:30".

    A weekday or bare time means the next such time after `now`.

    Raises:
        ValueError: unrecognised text.
    """
    match = _WHEN.match(text.strip())
    if not match:
        raise ValueError("use e.g. 'fri 19:00', 'tomorrow 12:30' or '2026-12-01 19:00'")
    tz = cfg.tz
    local_now = now.astimezone(tz)
    at_time = parse_hhmm(match.group("time"))
    day_word = (match.group("day") or "").lower()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", day_word):
        return datetime.combine(date.fromisoformat(day_word), at_time, tzinfo=tz)
    if day_word == "today":
        return datetime.combine(local_now.date(), at_time, tzinfo=tz)
    if day_word == "tomorrow":
        return datetime.combine(local_now.date() + timedelta(days=1), at_time, tzinfo=tz)
    for offset in range(8):
        day = local_now.date() + timedelta(days=offset)
        if day_word and WEEKDAYS[day.weekday()] != day_word:
            continue
        candidate = datetime.combine(day, at_time, tzinfo=tz)
        if candidate > local_now:
            return candidate
    raise ValueError(f"could not place {text!r}")  # pragma: no cover


def move_warnings(
    session: Session,
    cfg: CalendarConfig,
    kind: str,
    at: datetime,
    channels: set[str],
    exclude_id: int | None = None,
) -> list[str]:
    """Warnings for a manual move. Moves are allowed anyway (spec section 11)."""
    warnings: list[str] = []
    local = at.astimezone(cfg.tz)
    on_rhythm = any(
        s.at == local for s in slots_between(cfg, kind, local.date(), local.date())
    )
    if not on_rhythm:
        warnings.append(f"off-rhythm: {local:%a %H:%M} is not a {kind} slot")
    if WEEKDAYS[local.weekday()] in cfg.blackout_days and not on_rhythm:
        warnings.append(f"{local:%A} is a blackout day")
    rows = [r for r in _occupied(session, at, at) if r.id != exclude_id]
    at_utc = as_utc(at)
    filled = sum(1 for r in rows if r.kind == kind and as_utc(r.slot_at) == at_utc)
    spec = cfg.spec(kind)
    if filled >= spec.max:
        warnings.append(f"over max: slot already has {filled}/{spec.max}")
    clash = gap_conflict(cfg, at, channels, rows, exclude_id)
    if clash is not None:
        other = as_utc(clash.slot_at).astimezone(cfg.tz)
        warnings.append(
            f"within {cfg.min_gap_minutes} min of {clash.listing_code} at {other:%a %H:%M}"
        )
    return warnings
