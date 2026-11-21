"""Repository functions for the listing store. One function per use case."""

from __future__ import annotations

from typing import Literal

from sqlmodel import Session, select

from baby_arb.posting.tables import BotState, CodeCounter, utcnow

CodePrefix = Literal["P", "L", "C"]


def next_code(session: Session, prefix: CodePrefix) -> str:
    """Issue the next listing code for `prefix`, e.g. "P-0007".

    The counter row is updated inside the caller's transaction, so a rolled
    back intake does not burn a number.

    Args:
        session: Open session; the caller commits.
        prefix: P (own stock), L (seller listing) or C (content post).

    Returns:
        The new code, zero-padded to four digits.
    """
    counter = session.get(CodeCounter, prefix)
    if counter is None:
        counter = CodeCounter(prefix=prefix, last=0)
    counter.last += 1
    session.add(counter)
    session.flush()
    return f"{prefix}-{counter.last:04d}"


def get_flag(session: Session, key: str) -> str | None:
    """Return a bot_state value, or None when unset."""
    row = session.exec(select(BotState).where(BotState.key == key)).first()
    return row.value if row else None


def set_flag(session: Session, key: str, value: str) -> None:
    """Set a bot_state value (insert or update)."""
    row = session.get(BotState, key)
    if row is None:
        row = BotState(key=key, value=value)
    else:
        row.value = value
        row.updated_at = utcnow()
    session.add(row)


def is_paused(session: Session) -> bool:
    """True when an admin has sent /pause (scheduled jobs send nothing)."""
    return get_flag(session, "paused") == "1"
