"""Listing and schedule state machines (ENGINE_SPEC section 6).

Every change goes through `move_listing` or `move_schedule`, which refuse
transitions the spec does not allow and write a `listing_events` row with the
actor (admin Telegram ID, "cli" or "system").
"""

from __future__ import annotations

from sqlmodel import Session

from baby_arb.posting.tables import Listing, ListingEvent, ScheduleRow, utcnow

LISTING_TRANSITIONS: dict[str, frozenset[str]] = {
    "INTAKE": frozenset({"INTAKE", "SCREENED", "BLOCKED", "REJECTED"}),
    "SCREENED": frozenset({"SCREENED", "RENDERED", "BLOCKED", "REJECTED"}),
    "RENDERED": frozenset({"PREVIEW", "REJECTED"}),
    "PREVIEW": frozenset({"EDITING", "APPROVED", "REJECTED", "PREVIEW"}),
    # An edit that changes what the item is re-runs the safety screen.
    "EDITING": frozenset({"PREVIEW", "REJECTED", "BLOCKED"}),
    "APPROVED": frozenset({"APPROVED", "SCHEDULED"}),
    "SCHEDULED": frozenset({"SCHEDULED", "LIVE", "APPROVED"}),
    "LIVE": frozenset({"SOLD", "ARCHIVED"}),
    "SOLD": frozenset({"COLLECTED", "LIVE"}),
    "COLLECTED": frozenset({"ARCHIVED"}),
    "BLOCKED": frozenset(),
    "REJECTED": frozenset(),
    "ARCHIVED": frozenset(),
}

SCHEDULE_TRANSITIONS: dict[str, frozenset[str]] = {
    "PROPOSED": frozenset({"QUEUED", "SKIPPED", "PROPOSED"}),
    "QUEUED": frozenset({"POSTED", "MISSED", "SKIPPED", "QUEUED"}),
    "MISSED": frozenset({"QUEUED", "SKIPPED", "POSTED"}),
    "POSTED": frozenset(),
    "SKIPPED": frozenset(),
}


class TransitionError(ValueError):
    """A status change the spec does not allow."""


def move_listing(
    session: Session, listing: Listing, to: str, actor: str, note: str | None = None
) -> None:
    """Change a listing's status and log it (caller commits).

    Raises:
        TransitionError: `to` is not reachable from the current status.
    """
    current = listing.status
    if to not in LISTING_TRANSITIONS.get(current, frozenset()):
        raise TransitionError(f"{listing.code}: {current} -> {to} is not allowed")
    listing.status = to
    session.add(listing)
    session.add(
        ListingEvent(
            listing_code=listing.code, from_status=current, to_status=to, actor=actor, note=note
        )
    )


def move_schedule(
    session: Session, row: ScheduleRow, to: str, actor: str, note: str | None = None
) -> None:
    """Change a schedule row's status and log it under its listing (caller commits).

    Raises:
        TransitionError: `to` is not reachable from the current status.
    """
    current = row.status
    if to not in SCHEDULE_TRANSITIONS.get(current, frozenset()):
        raise TransitionError(f"schedule {row.id}: {current} -> {to} is not allowed")
    row.status = to
    if to == "POSTED":
        row.posted_at = utcnow()
    session.add(row)
    session.add(
        ListingEvent(
            listing_code=row.listing_code,
            from_status=f"schedule:{current}",
            to_status=f"schedule:{to}",
            actor=actor,
            note=note,
        )
    )
