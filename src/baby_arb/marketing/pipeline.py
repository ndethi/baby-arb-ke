"""The Phase 1 drop -> preview -> approve flow, shared by the bot and the CLI.

Each function does one admin step and returns what to show next. Nothing
here talks to Telegram, Meta or a buyer; the bot turns results into
messages. Hard rules enforced here:
- The price is the admin's. It is stored as given and only an admin edit
  changes it; the pricing check only adds a warning.
- BLOCK can never be approved and stops the flow before any render.
- REVIEW (including "recall not checked") renders straight to the preview with
  the reasons as a warning; the admin's Approve is the explicit override and
  is recorded on the verdict (`override_by`).
- A `#test` tag (or `mark_test`) flags a listing as a test so reports and
  later phases can leave it out.
- Phase 2 identify: when the admin gives no item name, the photos are read
  once (identify.py). A confident result fills the title "(auto)"; otherwise
  the bot asks "looks like X, right?". Corrections are logged as drift
  (`correct_model`). With a Brave key the item is then looked up once
  (lookup.py): facts with sources go into captions and the preview, and a
  Kenyan retailer price is offered as the "new from" anchor for the admin to
  accept. Nothing found online is used for the price.
- Model calls go through llm.py (captions, edit parsing) and degrade to
  templates or a question.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

from sqlmodel import Session, col, select

from baby_arb.marketing import captions as cap
from baby_arb.marketing import edits as ed
from baby_arb.marketing.calendar import (
    CalendarConfig,
    Slot,
    format_slot_line,
    move_warnings,
    next_free_slot,
    parse_when,
    slot_kind_for,
)
from baby_arb.marketing.identify import CATEGORIES, Identification, identify
from baby_arb.marketing.intake import (
    MAX_PHOTOS,
    ParsedLine,
    parse_line,
    parse_price,
    price_warnings,
)
from baby_arb.marketing.llm import complete
from baby_arb.marketing.lookup import LookupResult
from baby_arb.marketing.render.layout import TEMPLATE_VERSION, Layout, dump_layout, load_layout
from baby_arb.marketing.render.static import ListingView, RenderResult, render_listing
from baby_arb.marketing.states import move_listing, move_schedule
from baby_arb.posting.screen import screen
from baby_arb.posting.store import next_code
from baby_arb.posting.tables import (
    EditEvent,
    Listing,
    ListingEvent,
    Photo,
    Render,
    SafetyVerdictRow,
    ScheduleRow,
    as_utc,
    utcnow,
)

Renderer = Callable[[ListingView, dict[int, Path], Layout, Path], RenderResult]
Completer = Callable[..., Any]

ACTIVE_SCHEDULE = ("PROPOSED", "QUEUED", "MISSED")


class FlowError(ValueError):
    """An admin step that cannot happen now (message is shown to the admin)."""


@dataclass
class Need:
    """The flow is waiting for the admin."""

    code: str
    what: Literal["price", "title"]
    message: str


@dataclass
class Blocked:
    """The safety screen blocked the item. Final."""

    code: str
    reasons: list[str]


@dataclass
class Preview:
    """A rendered round ready to send for approval."""

    code: str
    round: int
    assets: list[Path]
    caption_ig: str
    caption_tiktok: str
    slot_line: str
    warnings: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    echo: list[str] = field(default_factory=list)
    needs_check: bool = False  # REVIEW reasons the admin confirms by approving
    is_test: bool = False
    info: list[str] = field(default_factory=list)  # identification and looked-up facts
    price_ref: int | None = None  # a sourced KE "new" price the admin may adopt


@dataclass
class Question:
    """The edit text was not understood; ask this."""

    code: str
    text: str


Step = Need | Blocked | Preview | Question


@dataclass
class Context:
    """Dependencies for a flow step (tests swap the renderer and the model)."""

    session: Session
    cfg: CalendarConfig
    assets_dir: Path
    actor: str
    now: datetime = field(default_factory=utcnow)
    renderer: Renderer = render_listing
    completer: Completer = complete
    # Phase 2: photo identification (default: identify.py through `completer`)
    # and online lookup (None: no Brave key, skipped).
    identifier: Callable[[list[Path]], Identification] | None = None
    lookup: Callable[[str, str | None], LookupResult] | None = None


# --------------------------------------------------------------------------- helpers

def get_listing(session: Session, code: str) -> Listing:
    """Load a listing by code (case-insensitive).

    Raises:
        FlowError: unknown code.
    """
    listing = session.get(Listing, code.upper())
    if listing is None:
        raise FlowError(f"No listing {code.upper()}.")
    return listing


def photos_of(session: Session, code: str) -> dict[int, Path]:
    """Photo number -> path."""
    rows = session.exec(select(Photo).where(Photo.listing_code == code)).all()
    return {r.n: Path(r.path) for r in rows}


def latest_verdict(session: Session, code: str) -> SafetyVerdictRow | None:
    """Most recent safety verdict for a listing."""
    return session.exec(
        select(SafetyVerdictRow)
        .where(SafetyVerdictRow.listing_code == code)
        .order_by(col(SafetyVerdictRow.id).desc())
    ).first()


def active_schedule(session: Session, code: str) -> ScheduleRow | None:
    """The listing's PROPOSED, QUEUED or MISSED schedule row, if any."""
    return session.exec(
        select(ScheduleRow)
        .where(ScheduleRow.listing_code == code, col(ScheduleRow.status).in_(ACTIVE_SCHEDULE))
        .order_by(col(ScheduleRow.id).desc())
    ).first()


def _content_kind(listing: Listing) -> str | None:
    return listing.category if listing.kind == "content" else None


def _view(listing: Listing) -> ListingView:
    return ListingView(
        code=listing.code,
        price=listing.price,
        grade=listing.grade,
        age_range=listing.age_range,
        ref_new_price=listing.ref_new_price,
        seller=listing.kind == "seller",
        content=listing.kind == "content",
    )


def _caption_input(listing: Listing) -> cap.CaptionInput:
    return cap.CaptionInput(
        code=listing.code,
        price=listing.price,
        title=listing.title,
        grade=listing.grade,
        age_range=listing.age_range,
        notes=listing.condition_note,
        ref_new_price=listing.ref_new_price,
        seller=listing.kind == "seller",
        content_kind=_content_kind(listing),
        facts=caption_facts(listing),
    )


CAPTION_FACT_MAX = 60


def caption_facts(listing: Listing) -> tuple[str, ...]:
    """Up to 3 short looked-up facts for captions.

    The preview shows every fact with its source; captions skip long values
    (often cut mid-sentence) and an online age range when the admin or the box
    already gave one, since shop pages can disagree with the item in hand.
    """
    out = []
    for fact in _facts(listing):
        if len(fact["value"]) > CAPTION_FACT_MAX:
            continue
        if fact["label"].lower().startswith("age") and listing.age_range:
            continue
        out.append(f"{fact['label']}: {fact['value']}")
    return tuple(out[:3])


def details_of(listing: Listing) -> dict[str, Any]:
    """listings.details as a dict."""
    data: dict[str, Any] = json.loads(listing.details) if listing.details else {}
    return data


def _set_details(listing: Listing, **values: Any) -> None:
    data = details_of(listing)
    data.update(values)
    listing.details = json.dumps(data)


def _facts(listing: Listing) -> list[dict[str, str]]:
    facts: list[dict[str, str]] = (details_of(listing).get("lookup") or {}).get("facts") or []
    return facts


def _price_ref(listing: Listing) -> dict[str, Any] | None:
    ref: dict[str, Any] | None = (details_of(listing).get("lookup") or {}).get("price_ref")
    return ref


def _save_photos(ctx: Context, code: str, photos: list[bytes]) -> None:
    folder = ctx.assets_dir / "raw" / code
    folder.mkdir(parents=True, exist_ok=True)
    for n, data in enumerate(photos, start=1):
        path = folder / f"{n:02d}.jpg"
        path.write_bytes(data)
        ctx.session.add(Photo(listing_code=code, n=n, path=str(path),
                              hash=hashlib.sha256(data).hexdigest(), is_hero=n == 1))


# --------------------------------------------------------------------------- intake

def strip_test_tag(line: str | None) -> tuple[str | None, bool]:
    """Remove a `#test` tag from a caption line; True when it was there."""
    if not line or not re.search(r"(?<!\w)#test\b", line, re.IGNORECASE):
        return line, False
    return " ".join(re.sub(r"(?<!\w)#test\b", " ", line, flags=re.IGNORECASE).split()), True


def intake(
    ctx: Context, photos: list[bytes], line: str | None, content_kind: str | None = None
) -> Step:
    """Create a listing from an album and its caption line, then advance.

    Args:
        ctx: Flow context.
        photos: 1 to 6 photo files, in album order.
        line: The caption line (own stock, `#seller ...`, or for content
            posts the post's one line).
        content_kind: teaser | tip | behind for `/post` content posts.

    Raises:
        FlowError: no photos or more than six.
    """
    if not photos:
        raise FlowError("Send 1 to 6 photos as one album with the caption line.")
    if len(photos) > MAX_PHOTOS:
        raise FlowError(f"Max {MAX_PHOTOS} photos per listing; got {len(photos)}.")
    line, is_test = strip_test_tag(line)
    if content_kind is not None:
        code = next_code(ctx.session, "C")
        listing = Listing(code=code, kind="content", status="INTAKE", category=content_kind,
                          title=(line or "").strip() or None, created_by=ctx.actor)
    else:
        parsed: ParsedLine = parse_line(line)
        code = next_code(ctx.session, "L" if parsed.kind == "seller" else "P")
        listing = Listing(
            code=code,
            kind=parsed.kind,
            status="INTAKE",
            grade=parsed.grade,
            age_range=parsed.age_range,
            condition_note=parsed.notes,
            buy_price=parsed.buy_price,
            price=parsed.price,
            price_source="admin" if parsed.price is not None else None,
            ref_new_price=parsed.ref_new_price,
            created_by=ctx.actor,
        )
    listing.layout = dump_layout(Layout(photo_order=list(range(1, len(photos) + 1))))
    listing.is_test = is_test
    ctx.session.add(listing)
    ctx.session.flush()
    _save_photos(ctx, code, photos)
    ctx.session.add(listing)
    ctx.session.commit()
    return advance(ctx, code)


def answer(ctx: Context, code: str, what: str, text: str) -> Step:
    """Record the admin's answer to a Need (price or title), then advance.

    Raises:
        FlowError: the answer is not usable (e.g. no price in the text).
    """
    listing = get_listing(ctx.session, code)
    if listing.status != "INTAKE":
        raise FlowError(f"{listing.code} is past intake ({listing.status}).")
    if what == "price":
        price = parse_price(text.split()[0]) if text.split() else None
        if price is None:
            raise FlowError("Reply with the price only, e.g. 2000 or 2.5k.")
        listing.price, listing.price_source = price, "admin"
    elif what == "title":
        title = " ".join(text.split())
        guess = (details_of(listing).get("identify") or {}).get("title")
        if guess and title.lower().strip(" .!") in YES_WORDS:
            title = guess
        elif len(title) < 3:
            raise FlowError("Reply with the item, e.g. 'Graco FastAction Fold stroller'.")
        elif guess and title.lower() != guess.lower():
            ctx.session.add(EditEvent(listing_code=listing.code, round=listing.round,
                                      raw_text=text, op="correct_model", target="title",
                                      before=guess, after=title, parsed_by="admin"))
        listing.title, listing.model_source = title, "admin"
    else:
        raise FlowError(f"Nothing to answer for {what}.")
    ctx.session.add(listing)
    ctx.session.commit()
    return advance(ctx, code)


def override(ctx: Context, code: str) -> Step:
    """Admin's explicit "yes, override" for a REVIEW verdict, then advance.

    Raises:
        FlowError: no REVIEW verdict to override (BLOCK can never be overridden).
    """
    listing = get_listing(ctx.session, code)
    verdict = latest_verdict(ctx.session, listing.code)
    if verdict is None or verdict.verdict != "REVIEW":
        raise FlowError(f"{listing.code} has no review to override.")
    verdict.override_by = ctx.actor
    ctx.session.add(verdict)
    ctx.session.commit()
    return advance(ctx, code)


def _screen(ctx: Context, listing: Listing) -> SafetyVerdictRow:
    # Our wording for a category key (e.g. "push walker"), never the model's.
    category = CATEGORIES.get(listing.category or "", listing.category)
    result = screen(listing.title, listing.condition_note, category)
    row = SafetyVerdictRow(listing_code=listing.code, verdict=result.verdict,
                           reasons=json.dumps(result.reasons),
                           recall_source=result.recall_source)
    previous = latest_verdict(ctx.session, listing.code)
    if (previous is not None and previous.override_by and result.verdict == "REVIEW"
            and set(result.reasons) <= set(json.loads(previous.reasons))):
        row.override_by = previous.override_by  # nothing new to review
    ctx.session.add(row)
    return row


def review_reasons(verdict: SafetyVerdictRow | None) -> list[str]:
    """Readable reasons of a REVIEW verdict not yet confirmed by an admin."""
    if verdict is None or verdict.verdict != "REVIEW" or verdict.override_by:
        return []
    return [r.replace("_", " ") for r in json.loads(verdict.reasons)]


def advance(ctx: Context, code: str) -> Step:
    """Run every step that needs no admin input; stop at the first that does."""
    listing = get_listing(ctx.session, code)
    if listing.status == "INTAKE":
        if listing.kind != "content":
            if listing.price is None:
                return Need(code, "price", f"{code}: what's the price? Reply with a number, "
                            "e.g. 2000. I never guess prices.")
            if not listing.title:
                need = _identify_once(ctx, listing)
                if need is not None:
                    return need
            _lookup_once(ctx, listing)
            verdict = _screen(ctx, listing)
            if verdict.verdict == "BLOCK":
                move_listing(ctx.session, listing, "BLOCKED", "system", verdict.reasons)
                ctx.session.commit()
                return Blocked(code, json.loads(verdict.reasons))
        move_listing(ctx.session, listing, "SCREENED", "system")
        ctx.session.commit()
    if listing.status == "SCREENED":
        return render_round(ctx, listing)
    raise FlowError(f"{code} is {listing.status}; nothing to advance.")


# --------------------------------------------------------------------------- identify

YES_WORDS = frozenset({"yes", "y", "yep", "yeah", "correct", "right", "ndio", "sawa", "ok"})


def _identify_once(ctx: Context, listing: Listing) -> Need | None:
    """Read the photos once; fill the title if confident, else ask (Need)."""
    found = details_of(listing).get("identify")
    if found is None:
        photos = [p for _, p in sorted(photos_of(ctx.session, listing.code).items())]
        ident = (ctx.identifier(photos) if ctx.identifier is not None
                 else identify(photos, ctx.completer))
        found = {"title": ident.title, "confidence": ident.confidence, "auto": ident.auto,
                 "category": ident.category, "brand": ident.brand, "model": ident.model,
                 "age_range": ident.age_range, "degraded": ident.degraded,
                 "reason": ident.reason}
        _set_details(listing, identify=found)
        if not ident.degraded:
            listing.brand, listing.model = ident.brand, ident.model
            listing.category = ident.category
            listing.model_confidence = Decimal(str(round(ident.confidence, 3)))
            if listing.age_range is None and ident.age_range:
                listing.age_range = ident.age_range
        if ident.auto:
            listing.title, listing.model_source = ident.title, "auto"
        ctx.session.add(listing)
        ctx.session.commit()
    if listing.title:
        return None
    guess = found.get("title")
    if guess:
        words = CATEGORIES.get(found.get("category") or "", "")
        kind = f" ({words})" if words and words.lower() not in guess.lower() else ""
        return Need(listing.code, "title", f"{listing.code}: looks like {guess}{kind}, right? "
                    "Reply 'yes', or the brand and model.")
    return Need(listing.code, "title", f"{listing.code}: what is it? Brand and model, e.g. "
                "'Graco FastAction Fold stroller'.")


def _lookup_once(ctx: Context, listing: Listing) -> None:
    """Look the item up online once, when a lookup is configured."""
    if ctx.lookup is None or not listing.title or "lookup" in details_of(listing):
        return
    result = ctx.lookup(listing.title, listing.brand)
    _set_details(listing, lookup=result.to_json())
    ctx.session.add(listing)
    ctx.session.commit()


def _info_lines(listing: Listing) -> list[str]:
    lines: list[str] = []
    found = details_of(listing).get("identify") or {}
    if listing.model_source == "auto" and listing.title:
        pct = round(float(found.get("confidence") or 0) * 100)
        lines.append(f"Item: {listing.title} (auto, {pct}%). Wrong? Edit: 'title <item>'.")
    for fact in _facts(listing):
        lines.append(f"{fact['label']}: {fact['value']} ({_host(fact['source'])})")
    ref = _price_ref(listing)
    if ref and ref.get("amount") != listing.ref_new_price:
        lines.append(f"Seen new at KES {ref['amount']:,} on {_host(ref['url'])}.")
    return lines


def _host(url: str) -> str:
    return (urlparse(url).hostname or url).removeprefix("www.")


def use_price_ref(ctx: Context, code: str) -> Step:
    """Admin adopts the looked-up KE price as the "new in Nairobi from" anchor.

    Raises:
        FlowError: nothing looked up, or the listing is not in preview.
    """
    listing = get_listing(ctx.session, code)
    ref = _price_ref(listing)
    if not ref:
        raise FlowError(f"{listing.code} has no looked-up price.")
    return edit(ctx, listing.code, f"ref {ref['amount']}")


# --------------------------------------------------------------------------- render

def _propose_slot(ctx: Context, listing: Listing) -> tuple[str, Slot | None]:
    row = active_schedule(ctx.session, listing.code)
    if row is not None:
        local = as_utc(row.slot_at).astimezone(ctx.cfg.tz)
        same = [r for r in ctx.session.exec(
            select(ScheduleRow).where(ScheduleRow.kind == row.kind,
                                      ScheduleRow.slot_at == row.slot_at,
                                      col(ScheduleRow.status).in_(("PROPOSED", "QUEUED",
                                                                   "POSTED")))
        ).all()]
        position = sorted(r.id or 0 for r in same).index(row.id or 0) + 1
        spec = ctx.cfg.spec(row.kind) if row.kind in ctx.cfg.slots else None
        label = next((sp.label for sp in ctx.cfg.specials
                      if sp.kind == row.kind and sp.date == local.date()), None)
        current = Slot(row.kind, local, spec.max if spec else len(same), len(same), label)
        return format_slot_line(current, position), current
    kind = slot_kind_for(listing.code, _content_kind(listing))
    slot = next_free_slot(ctx.session, ctx.cfg, kind, ctx.now)
    if slot is None:
        return (f"No free {kind} slot in the next {ctx.cfg.lookahead_days} days: "
                "use 🕒 Move or ⏭ Skip.", None)
    row = ScheduleRow(listing_code=listing.code, kind=kind, slot_at=slot.at,
                      channels=",".join(ctx.cfg.channels), status="PROPOSED",
                      proposed_by="system")
    ctx.session.add(row)
    ctx.session.flush()
    ctx.session.add(ListingEvent(listing_code=listing.code, from_status=None,
                                 to_status="schedule:PROPOSED", actor="system",
                                 note=slot.at.isoformat()))
    return format_slot_line(slot), slot


def render_round(ctx: Context, listing: Listing, echo: list[str] | None = None,
                 extra_issues: list[str] | None = None) -> Preview:
    """Render the next round, propose a slot and move the listing to PREVIEW."""
    if not listing.caption_ig or not listing.caption_tiktok:
        drafted = cap.draft_captions(_caption_input(listing), ctx.completer)
        listing.caption_ig, listing.caption_tiktok = drafted.ig, drafted.tiktok
    photos = photos_of(ctx.session, listing.code)
    layout = load_layout(listing.layout, sorted(photos))
    listing.round += 1
    out_dir = ctx.assets_dir / "ready" / listing.code / f"r{listing.round}"
    if out_dir.exists():
        shutil.rmtree(out_dir)
    result = ctx.renderer(_view(listing), photos, layout, out_dir)
    listing.template_version = TEMPLATE_VERSION
    listing.layout = dump_layout(layout)
    for name, path in result.paths.items():
        ctx.session.add(Render(listing_code=listing.code, round=listing.round, asset=name,
                               path=str(path), template_version=TEMPLATE_VERSION))
    if listing.status == "SCREENED":
        move_listing(ctx.session, listing, "RENDERED", "system")
    slot_line, _ = _propose_slot(ctx, listing)
    move_listing(ctx.session, listing, "PREVIEW", "system", f"round {listing.round}")
    ctx.session.commit()
    return _preview(ctx, listing, list(result.paths.values()), slot_line,
                    result.all_issues + (extra_issues or []), echo or [])


def show(ctx: Context, code: str) -> Preview:
    """Rebuild the latest preview without re-rendering (e.g. after a failed send).

    Raises:
        FlowError: the listing is not in preview.
    """
    listing = get_listing(ctx.session, code)
    if listing.status not in {"PREVIEW", "EDITING"}:
        raise FlowError(f"{listing.code} is {listing.status}; there is no preview to show.")
    slot_line, _ = _propose_slot(ctx, listing)
    ctx.session.commit()
    return _preview(ctx, listing, latest_assets(ctx.session, listing.code), slot_line, [], [])


def _preview(ctx: Context, listing: Listing, assets: list[Path], slot_line: str,
             issues: list[str], echo: list[str]) -> Preview:
    warnings = price_warnings(listing.price, listing.buy_price)
    verdict = latest_verdict(ctx.session, listing.code)
    pending = review_reasons(verdict)
    if pending:
        warnings.append("Check before approving: " + ", ".join(pending)
                        + ". Approve confirms you checked it.")
    if listing.is_test:
        warnings.insert(0, "TEST drop: not a real listing.")
    return Preview(
        code=listing.code,
        round=listing.round,
        assets=assets,
        caption_ig=listing.caption_ig or "",
        caption_tiktok=listing.caption_tiktok or "",
        slot_line=slot_line,
        warnings=warnings,
        issues=issues,
        echo=echo,
        needs_check=bool(pending),
        is_test=listing.is_test,
        info=_info_lines(listing),
        price_ref=(ref["amount"] if (ref := _price_ref(listing))
                   and ref.get("amount") != listing.ref_new_price else None),
    )


# --------------------------------------------------------------------------- edit

def _state(listing: Listing, photos: list[int]) -> dict[str, Any]:
    return {"code": listing.code, "price": listing.price, "title": listing.title,
            "grade": listing.grade, "age_range": listing.age_range,
            "condition_note": listing.condition_note, "photos": photos,
            "layout": json.loads(listing.layout) if listing.layout else {}}


def edit(ctx: Context, code: str, text: str) -> Step:
    """Apply the admin's plain-words edit and re-render (round N+1).

    Raises:
        FlowError: the listing is not in preview.
    """
    listing = get_listing(ctx.session, code)
    if listing.status not in {"PREVIEW", "EDITING"}:
        raise FlowError(f"{listing.code} is {listing.status}; only previews can be edited.")
    photos = sorted(photos_of(ctx.session, listing.code))
    plan = ed.parse_edit(text, _state(listing, photos), ctx.completer)
    if plan.question or not plan.ops:
        return Question(listing.code, plan.question or "What should change?")
    if listing.status == "PREVIEW":
        move_listing(ctx.session, listing, "EDITING", ctx.actor)

    field_names = ("price", "grade", "age_range", "condition_note", "title", "ref_new_price",
                   "buy_price")
    fields = {k: getattr(listing, k) for k in field_names}
    applied = ed.apply_layout_and_fields(
        plan.ops, fields, load_layout(listing.layout, photos),
        listing.caption_ig or "", listing.caption_tiktok or "",
    )
    for key in field_names:
        setattr(listing, key, applied.fields[key])
    if any(c.op.target == "price" for c in applied.changes if c.op.op == "set_field"):
        listing.price_source = "admin"
    for change in applied.changes:
        if (change.op.op == "set_field" and change.op.target == "title"
                and listing.model_source == "auto"):
            ctx.session.add(EditEvent(listing_code=listing.code, round=listing.round,
                                      raw_text=text, op="correct_model", target="title",
                                      before=change.before, after=change.after,
                                      parsed_by=plan.parsed_by))
    if any(c.op.target == "title" for c in applied.changes if c.op.op == "set_field"):
        listing.model_source = "admin"
    listing.layout = dump_layout(applied.layout)
    listing.caption_ig, listing.caption_tiktok = applied.caption_ig, applied.caption_tiktok
    problems = list(applied.problems)
    if applied.fields_changed:
        drafted = cap.draft_captions(_caption_input(listing), ctx.completer)
        listing.caption_ig, listing.caption_tiktok = drafted.ig, drafted.tiktok
    for op in plan.ops:
        if op.op == "rewrite_caption" and not str(op.value).startswith(ed.REMOVE_PREFIX):
            for platform in ("ig", "tiktok"):
                if op.target not in (platform, "all"):
                    continue
                attr = f"caption_{platform}"
                before = getattr(listing, attr) or ""
                after, issues = cap.rewrite_caption(before, platform, str(op.value),
                                                    _caption_input(listing), ctx.completer)
                setattr(listing, attr, after)
                problems += [f"{platform} caption kept: {i}" for i in issues]
                applied.changes.append(ed.Change(op, before, after))
    for change in applied.changes:
        ctx.session.add(EditEvent(
            listing_code=listing.code, round=listing.round, raw_text=text, op=change.op.op,
            target=change.op.target, before=change.before, after=change.after,
            parsed_by=plan.parsed_by,
        ))

    if listing.kind != "content" and any(
        c.op.op == "set_field" and c.op.target in {"title", "condition_note"}
        for c in applied.changes
    ):
        verdict = _screen(ctx, listing)
        if verdict.verdict == "BLOCK":
            move_listing(ctx.session, listing, "BLOCKED", "system", verdict.reasons)
            _drop_schedule(ctx, listing.code, "blocked")
            ctx.session.commit()
            return Blocked(listing.code, json.loads(verdict.reasons))
    ctx.session.add(listing)
    ctx.session.flush()
    return render_round(ctx, listing, echo=[ed.describe(o) for o in plan.ops],
                        extra_issues=problems)


# --------------------------------------------------------------------------- decisions

def _drop_schedule(ctx: Context, code: str, note: str) -> None:
    row = active_schedule(ctx.session, code)
    if row is not None:
        move_schedule(ctx.session, row, "SKIPPED", ctx.actor, note)


def _check_approvable(ctx: Context, listing: Listing) -> None:
    if listing.status != "PREVIEW":
        raise FlowError(f"{listing.code} is {listing.status}; only a preview can be approved.")
    if listing.kind == "content":
        return
    if listing.price is None:
        raise FlowError(f"{listing.code} has no price.")
    verdict = latest_verdict(ctx.session, listing.code)
    if verdict is None:
        raise FlowError(f"{listing.code} has not been safety screened.")
    if verdict.verdict == "BLOCK":
        raise FlowError(f"{listing.code} is BLOCKED and can never be approved.")
    if verdict.verdict == "REVIEW" and not verdict.override_by:
        # Approving (or skipping into APPROVED) is the admin's explicit check.
        verdict.override_by = ctx.actor
        ctx.session.add(verdict)


def approve(ctx: Context, code: str, now: bool = False) -> str:
    """✅ Approve (proposed slot) or ⏩ Now. Returns the confirmation text.

    Raises:
        FlowError: not approvable (BLOCK, un-overridden REVIEW, no slot...).
    """
    listing = get_listing(ctx.session, code)
    _check_approvable(ctx, listing)
    row = active_schedule(ctx.session, listing.code)
    if now:
        if row is None:
            kind = slot_kind_for(listing.code, _content_kind(listing))
            row = ScheduleRow(listing_code=listing.code, kind=kind, slot_at=ctx.now,
                              channels=",".join(ctx.cfg.channels), status="PROPOSED",
                              proposed_by="admin")
            ctx.session.add(row)
            ctx.session.flush()
        else:
            row.moved_from, row.slot_at, row.proposed_by = row.slot_at, ctx.now, "admin"
    elif row is None:
        raise FlowError(f"{listing.code} has no slot. Use 🕒 Move to pick one, or ⏭ Skip.")
    move_listing(ctx.session, listing, "APPROVED", ctx.actor)
    move_schedule(ctx.session, row, "QUEUED", ctx.actor, "now" if now else None)
    move_listing(ctx.session, listing, "SCHEDULED", ctx.actor)
    ctx.session.commit()
    if now:
        return f"✅ {listing.code} approved for now. Files and captions are on the way."
    local = as_utc(row.slot_at).astimezone(ctx.cfg.tz)
    return f"✅ {listing.code} approved and queued for {local:%a %d %b %H:%M}."


def skip(ctx: Context, code: str) -> str:
    """⏭ Skip: keep (or make) the listing APPROVED with no slot.

    Raises:
        FlowError: wrong status.
    """
    listing = get_listing(ctx.session, code)
    if listing.status == "PREVIEW":
        _check_approvable(ctx, listing)
        _drop_schedule(ctx, listing.code, "skip")
        move_listing(ctx.session, listing, "APPROVED", ctx.actor, "skip: no slot")
    elif listing.status == "SCHEDULED":
        _drop_schedule(ctx, listing.code, "skip")
        move_listing(ctx.session, listing, "APPROVED", ctx.actor, "skip: no slot")
    elif listing.status != "APPROVED":
        raise FlowError(f"{listing.code} is {listing.status}; can't skip.")
    ctx.session.commit()
    return f"⏭ {listing.code} approved with no slot. Use 'move {listing.code} fri 19:00' later."


def reject(ctx: Context, code: str, reason: str | None) -> str:
    """❌ Reject with an optional reason (logged as drift, op=reject).

    Raises:
        FlowError: wrong status.
    """
    listing = get_listing(ctx.session, code)
    if listing.status not in {"INTAKE", "SCREENED", "RENDERED", "PREVIEW", "EDITING"}:
        raise FlowError(f"{listing.code} is {listing.status}; can't reject.")
    _drop_schedule(ctx, listing.code, "rejected")
    move_listing(ctx.session, listing, "REJECTED", ctx.actor, reason)
    ctx.session.add(EditEvent(listing_code=listing.code, round=listing.round,
                              raw_text=reason or "", op="reject", parsed_by="admin"))
    ctx.session.commit()
    return f"❌ {listing.code} rejected." + (f" Reason noted: {reason}" if reason else "")


def move(ctx: Context, code: str, when: str) -> str:
    """🕒 Move to a time ("fri 19:00"). Warns if off-rhythm or over max; allows it.

    Raises:
        FlowError: unreadable time, past time or wrong status.
    """
    listing = get_listing(ctx.session, code)
    if listing.status not in {"PREVIEW", "APPROVED", "SCHEDULED"}:
        raise FlowError(f"{listing.code} is {listing.status}; can't move.")
    try:
        at = parse_when(when, ctx.now, ctx.cfg)
    except ValueError as exc:
        raise FlowError(str(exc)) from exc
    if at <= ctx.now:
        raise FlowError("That time has passed.")
    kind = slot_kind_for(listing.code, _content_kind(listing))
    row = active_schedule(ctx.session, listing.code)
    channels = set(ctx.cfg.channels)
    warnings = move_warnings(ctx.session, ctx.cfg, kind, at, channels,
                             row.id if row is not None else None)
    if row is None:
        status = "QUEUED" if listing.status == "APPROVED" else "PROPOSED"
        row = ScheduleRow(listing_code=listing.code, kind=kind, slot_at=at,
                          channels=",".join(ctx.cfg.channels), status="PROPOSED",
                          proposed_by="admin")
        ctx.session.add(row)
        ctx.session.flush()
        if status == "QUEUED":
            move_schedule(ctx.session, row, "QUEUED", ctx.actor, "move")
            move_listing(ctx.session, listing, "SCHEDULED", ctx.actor)
    else:
        row.moved_from, row.slot_at, row.proposed_by = row.slot_at, at, "admin"
        row.reminded_at = None
        if row.status == "MISSED":
            move_schedule(ctx.session, row, "QUEUED", ctx.actor, "re-slotted")
        else:
            move_schedule(ctx.session, row, row.status, ctx.actor, f"moved to {at.isoformat()}")
    ctx.session.commit()
    text = f"🕒 {listing.code} moved to {at.astimezone(ctx.cfg.tz):%a %d %b %H:%M}."
    if warnings:
        text += "\n⚠️ " + "\n⚠️ ".join(warnings)
    return text


def reslot(ctx: Context, code: str) -> str:
    """Put a MISSED post into the next free slot of its kind.

    Raises:
        FlowError: nothing missed, or no free slot.
    """
    listing = get_listing(ctx.session, code)
    row = active_schedule(ctx.session, listing.code)
    if row is None or row.status != "MISSED":
        raise FlowError(f"{listing.code} has no missed slot.")
    slot = next_free_slot(ctx.session, ctx.cfg, row.kind, ctx.now)
    if slot is None:
        raise FlowError(f"No free {row.kind} slot in {ctx.cfg.lookahead_days} days; use move.")
    row.moved_from, row.slot_at, row.reminded_at = row.slot_at, slot.at, None
    move_schedule(ctx.session, row, "QUEUED", ctx.actor, "re-slotted")
    ctx.session.commit()
    return f"🕒 {listing.code} re-slotted: {format_slot_line(slot)}"


def posted(ctx: Context, code: str) -> str:
    """Mark a hand-posted listing as posted (Phases 1-2): schedule POSTED, listing LIVE.

    Raises:
        FlowError: nothing queued for this listing.
    """
    listing = get_listing(ctx.session, code)
    row = active_schedule(ctx.session, listing.code)
    if row is None or row.status not in {"QUEUED", "MISSED"}:
        raise FlowError(f"{listing.code} has nothing queued to mark posted.")
    move_schedule(ctx.session, row, "POSTED", ctx.actor)
    if listing.status == "APPROVED":
        move_listing(ctx.session, listing, "SCHEDULED", ctx.actor)
    move_listing(ctx.session, listing, "LIVE", ctx.actor)
    listing.live_at = utcnow()
    ctx.session.commit()
    return f"📣 {listing.code} marked posted. It's live."


def latest_assets(session: Session, code: str) -> list[Path]:
    """Asset paths of the listing's latest round, feed first."""
    listing = get_listing(session, code)
    rows = session.exec(
        select(Render).where(Render.listing_code == listing.code, Render.round == listing.round)
        .order_by(col(Render.id))
    ).all()
    return [Path(r.path) for r in rows]


CLOSABLE = ("INTAKE", "SCREENED", "RENDERED", "PREVIEW", "EDITING", "APPROVED", "SCHEDULED")


def mark_test(ctx: Context, code: str) -> str:
    """Flag a listing as a test and close it if it has not gone live.

    Not logged as drift: a test is not an admin judgement on the content.

    Raises:
        FlowError: unknown code.
    """
    listing = get_listing(ctx.session, code)
    listing.is_test = True
    closed = ""
    if listing.status in CLOSABLE:
        row = active_schedule(ctx.session, listing.code)
        if row is not None:
            move_schedule(ctx.session, row, "SKIPPED", ctx.actor, "test drop")
        listing.status, before = "REJECTED", listing.status
        ctx.session.add(ListingEvent(listing_code=listing.code, from_status=before,
                                     to_status="REJECTED", actor=ctx.actor, note="test drop"))
        closed = " and closed"
    ctx.session.add(listing)
    ctx.session.commit()
    return f"🧪 {listing.code} marked as a test{closed}."
