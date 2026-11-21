"""`baby-arb mkt ...` and `baby-arb bot ...` commands.

Every command works without Telegram so it can be run by hand, by tests and
by Hermes cron (no-agent jobs).
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from baby_arb.config import get_settings
from baby_arb.storage.migrate import run_migrations

console = Console()

mkt_app = typer.Typer(help="Marketing engine commands (docs/marketing/ENGINE_SPEC.md).")
bot_app = typer.Typer(help="Shop Telegram bot.")

@bot_app.command("run")
def bot_run() -> None:
    """Run the shop bot (long polling). Answers allow-listed admins only."""
    from baby_arb.marketing.bot.app import BotNotConfiguredError, build_application

    try:
        app = build_application(get_settings())
    except BotNotConfiguredError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    console.print("[green]babyReShop bot running. Ctrl-C to stop.[/green]")
    app.run_polling()


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
    console.print(f"[green]{result.provider} / {result.model}:[/green] {result.text}")


def db_upgrade(
    url: Annotated[str | None, typer.Option(help="Database URL (default: DATABASE_URL)")] = None,
) -> None:
    """Create or migrate the database to the latest schema."""
    target = url or get_settings().database_url
    if target.startswith("sqlite:///"):
        Path(target.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
    run_migrations(url)
    console.print(f"[green]Database at head:[/green] {target}")
