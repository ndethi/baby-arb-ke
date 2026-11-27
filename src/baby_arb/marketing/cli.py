"""`baby-arb mkt ...` and `baby-arb bot ...` commands.

Every command works without Telegram so it can be run by hand, by tests and
by Hermes cron (no-agent jobs).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import date
from pathlib import Path
from typing import Annotated, Any, TypeVar

import typer
from rich.console import Console
from sqlmodel import Session

from baby_arb.config import get_settings
from baby_arb.storage.migrate import run_migrations

console = Console()

mkt_app = typer.Typer(help="Marketing engine commands (docs/marketing/ENGINE_SPEC.md).")
cal_app = typer.Typer(help="Content calendar (config/calendar.yaml).")
mkt_app.add_typer(cal_app, name="cal")
bot_app = typer.Typer(help="Shop Telegram bot.")

T = TypeVar("T")
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def _run(fn: Callable[[Any], T]) -> T:
    """Run a pipeline step as actor "cli"; FlowError exits with code 1."""
    from functools import partial

    from baby_arb.marketing import pipeline as pl
    from baby_arb.marketing.calendar import load_config
    from baby_arb.marketing.render.static import render_listing
    from baby_arb.posting.tables import utcnow
    from baby_arb.storage.db import get_engine

    settings = get_settings()
    with Session(get_engine(settings.database_url)) as session:
        ctx = pl.Context(
            session=session, cfg=load_config(), assets_dir=Path(settings.marketing_assets_dir),
            actor="cli", now=utcnow(),
            renderer=partial(render_listing, channel=settings.render_browser_channel),
        )
        try:
            return fn(ctx)
        except pl.FlowError as exc:
            console.print(f"[red]{exc}[/red]", emoji=False)
            raise typer.Exit(code=1) from exc


def _show(result: object) -> None:
    from baby_arb.marketing import pipeline as pl

    if isinstance(result, str):
        console.print(result, emoji=False)
    elif isinstance(result, pl.Need):
        console.print(f"[yellow]Needs {result.what}:[/yellow] {result.message}", emoji=False)
    elif isinstance(result, pl.Blocked):
        console.print(f"[red]BLOCKED {result.code}:[/red] {', '.join(result.reasons)}")
    elif isinstance(result, pl.Question):
        console.print(f"[yellow]{result.code}:[/yellow] {result.text}", emoji=False)
    elif isinstance(result, pl.Preview):
        console.print(f"[green]{result.code} round {result.round}[/green] · {result.slot_line}",
                      emoji=False)
        for line in result.echo:
            console.print(f"  applied: {line}", emoji=False)
        for line in result.warnings + result.issues:
            console.print(f"  [yellow]! {line}[/yellow]", emoji=False)
        for path in result.assets:
            console.print(f"  {path}")
        console.print(f"\nIG + FB:\n{result.caption_ig}\n\nTikTok:\n{result.caption_tiktok}",
                      emoji=False)


def _album(folder: Path) -> list[bytes]:
    files = sorted(p for p in folder.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES)
    return [p.read_bytes() for p in files]


@mkt_app.command("intake")
def mkt_intake(
    album: Annotated[Path, typer.Option(exists=True, file_okay=False, help="Photo folder")],
    line: Annotated[str, typer.Option(help="Caption line, e.g. '2000 B 0-36m washed'")] = "",
    post: Annotated[str | None, typer.Option(help="Content post kind: teaser|tip|behind")] = None,
) -> None:
    """New listing from a folder of 1-6 photos and the caption line."""
    from baby_arb.marketing import pipeline as pl

    photos = _album(album)
    _show(_run(lambda ctx: pl.intake(ctx, photos, line, post)))


@mkt_app.command("answer")
def mkt_answer(
    code: str,
    what: Annotated[str, typer.Argument(help="price | title")],
    text: str,
) -> None:
    """Answer the bot's question for a listing in intake (price or title)."""
    from baby_arb.marketing import pipeline as pl

    _show(_run(lambda ctx: pl.answer(ctx, code, what, text)))


@mkt_app.command("override")
def mkt_override(code: str) -> None:
    """Admin override of a REVIEW safety verdict (never possible for BLOCK)."""
    from baby_arb.marketing import pipeline as pl

    _show(_run(lambda ctx: pl.override(ctx, code)))


@mkt_app.command("test")
def mkt_test(code: str) -> None:
    """Flag a listing as a test drop (closed unless already live)."""
    from baby_arb.marketing import pipeline as pl

    _show(_run(lambda ctx: pl.mark_test(ctx, code)))


@mkt_app.command("render")
def mkt_render(code: str) -> None:
    """Render the next round of a listing in preview."""
    from baby_arb.marketing import pipeline as pl

    def go(ctx: Any) -> object:
        listing = pl.get_listing(ctx.session, code)
        if listing.status != "PREVIEW":
            raise pl.FlowError(f"{listing.code} is {listing.status}; render needs PREVIEW.")
        return pl.render_round(ctx, listing)

    _show(_run(go))


@mkt_app.command("edit")
def mkt_edit(code: str, text: Annotated[str, typer.Option(help="The admin's words")]) -> None:
    """Apply plain-words edits and re-render."""
    from baby_arb.marketing import pipeline as pl

    _show(_run(lambda ctx: pl.edit(ctx, code, text)))


@mkt_app.command("approve")
def mkt_approve(
    code: str,
    at: Annotated[str | None, typer.Option(help="Move first, e.g. 'fri 19:00'")] = None,
    now: Annotated[bool, typer.Option(help="Queue for immediate posting")] = False,
) -> None:
    """Approve a preview into its slot (or --at a time, or --now)."""
    from baby_arb.marketing import pipeline as pl

    def go(ctx: Any) -> str:
        moved = pl.move(ctx, code, at) + "\n" if at else ""
        return moved + pl.approve(ctx, code, now=now)

    _show(_run(go))


@mkt_app.command("reject")
def mkt_reject(code: str, reason: Annotated[str | None, typer.Option()] = None) -> None:
    """Reject a listing (the reason is logged as drift)."""
    from baby_arb.marketing import pipeline as pl

    _show(_run(lambda ctx: pl.reject(ctx, code, reason)))


@cal_app.command("next")
def cal_next(kind: str) -> None:
    """Show the next free slot of a kind."""
    from baby_arb.marketing.calendar import format_slot_line, load_config, next_free_slot
    from baby_arb.posting.tables import utcnow
    from baby_arb.storage.db import get_engine

    cfg = load_config()
    with Session(get_engine(get_settings().database_url)) as session:
        slot = next_free_slot(session, cfg, kind, utcnow())
    console.print(format_slot_line(slot) if slot else f"No free {kind} slot in "
                  f"{cfg.lookahead_days} days.", emoji=False)


@cal_app.command("week")
def cal_week(
    start: Annotated[str | None, typer.Option(help="Any date in the week, YYYY-MM-DD")] = None,
) -> None:
    """This week's slots: filled, empty, capacity."""
    from baby_arb.marketing.calendar import format_week, load_config, week_view
    from baby_arb.posting.tables import utcnow
    from baby_arb.storage.db import get_engine

    cfg = load_config()
    day = date.fromisoformat(start) if start else utcnow().astimezone(cfg.tz).date()
    with Session(get_engine(get_settings().database_url)) as session:
        console.print(format_week(week_view(session, cfg, day)), emoji=False)


@cal_app.command("assign")
def cal_assign(code: str, at: Annotated[str, typer.Option(help="e.g. 'fri 19:00'")]) -> None:
    """Give a listing a slot at a time (same as move)."""
    from baby_arb.marketing import pipeline as pl

    _show(_run(lambda ctx: pl.move(ctx, code, at)))


@cal_app.command("move")
def cal_move(code: str, when: str) -> None:
    """Move a listing's slot, e.g. `cal move P-0007 "fri 19:00"`."""
    from baby_arb.marketing import pipeline as pl

    _show(_run(lambda ctx: pl.move(ctx, code, when)))


@cal_app.command("skip")
def cal_skip(code: str) -> None:
    """Take a listing off the calendar; it stays APPROVED."""
    from baby_arb.marketing import pipeline as pl

    _show(_run(lambda ctx: pl.skip(ctx, code)))


@cal_app.command("posted")
def cal_posted(code: str) -> None:
    """Mark a hand-posted listing as posted (LIVE)."""
    from baby_arb.marketing import pipeline as pl

    _show(_run(lambda ctx: pl.posted(ctx, code)))


class PrintNotifier:
    """--dry-run: print what tick would send."""

    def send_message(self, chat_id: int, text: str, reply_markup: Any = None) -> dict[str, Any]:
        """Print a message."""
        console.print(f"[dim]→ {chat_id}[/dim] {text}", emoji=False)
        return {}

    def send_media_group(
        self, chat_id: int, paths: Sequence[Path], caption: str | None = None
    ) -> list[dict[str, Any]]:
        """Print an album."""
        console.print(f"[dim]→ {chat_id}[/dim] album: {', '.join(p.name for p in paths)}")
        return []


@cal_app.command("tick")
def cal_tick(
    dry_run: Annotated[bool, typer.Option(help="Print instead of sending")] = False,
) -> None:
    """Reminders, MISSED and scheduled messages. Idempotent; silent when idle."""
    from baby_arb.marketing.bot.auth import Access
    from baby_arb.marketing.bot.send import OpsSender
    from baby_arb.marketing.calendar import load_config
    from baby_arb.marketing.tick import Notifier, tick
    from baby_arb.posting.tables import utcnow
    from baby_arb.storage.db import get_engine

    settings = get_settings()
    if settings.telegram_ops_chat_id is None:
        console.print("[red]TELEGRAM_OPS_CHAT_ID is not set[/red]")
        raise typer.Exit(code=1)
    notifier: Notifier
    if dry_run:
        notifier = PrintNotifier()
    else:
        if not settings.telegram_bot_token:
            console.print("[red]TELEGRAM_BOT_TOKEN is not set[/red]")
            raise typer.Exit(code=1)
        notifier = OpsSender(settings.telegram_bot_token, Access.from_settings(settings))
    with Session(get_engine(settings.database_url)) as session:
        done = tick(session, load_config(), notifier, settings.telegram_ops_chat_id, utcnow())
    for line in done:  # empty output when nothing happened (Hermes no_agent stays silent)
        console.print(line)


@bot_app.command("run")
def bot_run(
    tick_loop: Annotated[bool, typer.Option("--tick/--no-tick",
                                            help="Run cal tick every 5 min")] = True,
) -> None:
    """Run the shop bot (long polling). Answers allow-listed admins only."""
    from telegram import Update

    from baby_arb.marketing.bot.app import BotNotConfiguredError, build_application

    try:
        app = build_application(get_settings(), tick_enabled=tick_loop)
    except BotNotConfiguredError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    console.print("[green]babyReShop bot running. Ctrl-C to stop.[/green]")
    # Ask for every update type: Telegram keeps the last allowed_updates filter, and an
    # earlier messages-only getUpdates call had silently turned off button presses.
    app.run_polling(allowed_updates=Update.ALL_TYPES)


@mkt_app.command("llm-check")
def llm_check() -> None:
    """Send one tiny prompt through llm.py to confirm keys and the cap work."""
    from baby_arb.marketing.llm import complete

    result = complete(
        "llm_check",
        [{"role": "user", "content": "Reply with the single word: ready"}],
        max_tokens=10,
    )
    if result.degraded:
        console.print(f"[yellow]Degraded: {result.reason}[/yellow]")
        raise typer.Exit(code=1)
    console.print(f"[green]{result.provider} / {result.model}:[/green] {result.text}", emoji=False)


def db_upgrade(
    url: Annotated[str | None, typer.Option(help="Database URL (default: DATABASE_URL)")] = None,
) -> None:
    """Create or migrate the database to the latest schema."""
    target = url or get_settings().database_url
    if target.startswith("sqlite:///"):
        Path(target.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
    run_migrations(url)
    console.print(f"[green]Database at head:[/green] {target}")
