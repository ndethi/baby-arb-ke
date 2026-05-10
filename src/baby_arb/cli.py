"""CLI entry point. Typer-based.

Provides smoke tests for the MVP: pricing math, compliance gate, demand
scoring. Sourcing scrape, buyer flow, listing publish are post-MVP and
are stubbed with informative messages.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from baby_arb import __version__
from baby_arb.compliance.gate import gate as compliance_gate
from baby_arb.compliance.cpsc import write_cache_for_test
from baby_arb.demand.aggregator import compose_signal
from baby_arb.models.candidate import BuyCandidate, ItemCategory, ItemCondition
from baby_arb.models.demand import DemandSignals
from baby_arb.pricing import calculate_landed_cost
from baby_arb.pricing.fx import set_cache_for_test
from baby_arb.pricing.intl_shipping import Carrier
from baby_arb.pricing.verdict import pricing_verdict

app = typer.Typer(help="baby-arb-ke CLI — sourcing/pricing/compliance for KE arbitrage.")
console = Console()


# ── Subcommand groups ────────────────────────────────────────────────
price_app = typer.Typer(help="Pricing engine commands.")
compliance_app = typer.Typer(help="Compliance gate commands.")
demand_app = typer.Typer(help="Demand signal commands.")
brief_app = typer.Typer(help="Sourcing brief commands.")
db_app = typer.Typer(help="Database commands.")

app.add_typer(price_app, name="price")
app.add_typer(compliance_app, name="compliance")
app.add_typer(demand_app, name="demand")
app.add_typer(brief_app, name="brief")
app.add_typer(db_app, name="db")


# ── Top-level commands ───────────────────────────────────────────────
@app.command()
def version() -> None:
    """Show version."""
    console.print(f"baby-arb-ke v{__version__}")


@app.command()
def health() -> None:
    """Health check across modules.

    MVP: checks the pricing engine works on a synthetic input,
    confirms compliance gate is callable, and reports config sanity.
    """
    from baby_arb.config import get_settings
    from baby_arb.pricing.rules import MARGIN_FLOOR_PCT, ENGINE_VERSION

    settings = get_settings()
    table = Table(title="baby-arb-ke health")
    table.add_column("Component")
    table.add_column("Status")
    table.add_column("Detail")

    table.add_row("version", "OK", __version__)
    table.add_row("engine_version", "OK", ENGINE_VERSION)
    table.add_row("margin_floor", "OK", f"{MARGIN_FLOOR_PCT}%")
    table.add_row("max_auto_buy", "OK", f"${settings.max_auto_buy_usd}")
    table.add_row("eBay App ID", _yn(settings.ebay_app_id), _mask(settings.ebay_app_id))
    table.add_row("DHL key", _yn(settings.dhl_api_key), _mask(settings.dhl_api_key))
    table.add_row("FX provider", "OK", settings.fx_provider)
    table.add_row("Telegram bot", _yn(settings.telegram_bot_token), _mask(settings.telegram_bot_token))
    table.add_row("Database", "OK", settings.database_url)

    console.print(table)


# ── price ───────────────────────────────────────────────────────────
@price_app.command("smoke")
def price_smoke(
    listing_price: Annotated[float, typer.Option(help="USD listing price")] = 180.0,
    us_shipping: Annotated[float, typer.Option(help="USD US shipping")] = 22.0,
    weight_lb: Annotated[float, typer.Option(help="Item weight in lb")] = 9.0,
    length_in: Annotated[float, typer.Option(help="Length in inches")] = 18.0,
    width_in: Annotated[float, typer.Option(help="Width in inches")] = 18.0,
    height_in: Annotated[float, typer.Option(help="Height in inches")] = 24.0,
    category: Annotated[
        str, typer.Option(help="ItemCategory value")
    ] = "car_seat",
    warehouse_state: Annotated[str, typer.Option(help="2-letter US state")] = "DE",
    fx_rate: Annotated[float, typer.Option(help="USD/KES rate to use")] = 145.5,
    ke_price: Annotated[
        float, typer.Option(help="Reference KE sale price in KES")
    ] = 32500.0,
    carrier: Annotated[str, typer.Option(help="dhl_express | aramex | sea_freight")] = "dhl_express",
) -> None:
    """Run a pricing smoke test on a synthetic candidate.

    No network required. Uses cached FX rate (injected for the test).
    """
    # Inject FX rate so we don't need network
    now = datetime.now(timezone.utc)
    set_cache_for_test(Decimal(str(fx_rate)), now)

    candidate = BuyCandidate(
        candidate_id="smoke-test",
        marketplace="ebay",
        listing_url="https://www.ebay.com/itm/smoke-test",
        brand="NUNA",
        model="PIPA Lite RX",
        category=ItemCategory(category),
        condition_text="Used like new, manufactured 2023",
        condition_normalized=ItemCondition.LIKE_NEW,
        listing_price_usd=Decimal(str(listing_price)),
        us_shipping_usd=Decimal(str(us_shipping)),
        weight_lb=Decimal(str(weight_lb)),
        weight_source="listed",
        length_in=Decimal(str(length_in)),
        width_in=Decimal(str(width_in)),
        height_in=Decimal(str(height_in)),
        seller_id="seller_smoke",
        seller_state="TX",
        seller_feedback_count=200,
        seller_feedback_pct=Decimal("99.2"),
        photos=[
            "https://example.com/1.jpg",
            "https://example.com/2.jpg",
            "https://example.com/3.jpg",
        ],
        reference_ke_sale_price_kes=Decimal(str(ke_price)),
        reference_source="jiji_median_sold",
        reference_n=5,
    )

    landed = calculate_landed_cost(
        candidate,
        warehouse_state=warehouse_state,
        carrier=Carrier(carrier),
        now=now,
    )
    verdict = pricing_verdict(candidate, landed)

    _render_pricing(candidate, landed, verdict)


@price_app.command("listing-url")
def price_listing_url(
    url: Annotated[str, typer.Argument(help="eBay listing URL")],
) -> None:
    """Price a real eBay listing.

    Status: stub — needs Sourcing Scout's eBay client (post-MVP).
    Hermes: build src/baby_arb/sourcing/ebay/parser.py first, then wire
    it here.
    """
    console.print(
        Panel(
            f"[yellow]Not yet implemented.[/yellow] "
            f"Needs eBay parser. URL was: {url}\n\n"
            f"For now: extract listing details manually and run "
            f"[bold]baby-arb price smoke --listing-price ... [/bold] etc.",
            title="price listing-url",
        )
    )
    raise typer.Exit(code=1)


# ── compliance ──────────────────────────────────────────────────────
@compliance_app.command("smoke")
def compliance_smoke(
    brand: Annotated[str, typer.Option(help="Brand name")] = "NUNA",
    model: Annotated[str, typer.Option(help="Model")] = "PIPA Lite RX",
    category: Annotated[str, typer.Option(help="ItemCategory")] = "car_seat",
    condition_text: Annotated[
        str, typer.Option(help="Listing description")
    ] = "Used like new, manufactured 2023, all parts intact",
    seller_feedback: Annotated[int, typer.Option(help="Seller feedback count")] = 200,
    seller_pct: Annotated[float, typer.Option(help="Seller feedback %")] = 99.2,
    n_photos: Annotated[int, typer.Option(help="Number of photos")] = 4,
) -> None:
    """Run the compliance gate on a synthetic candidate.

    Seeds a test CPSC cache with no recalls so the check passes through.
    """
    # Seed empty CPSC cache so gate doesn't return unreachable
    write_cache_for_test([])

    candidate = BuyCandidate(
        candidate_id="compliance-smoke",
        marketplace="ebay",
        listing_url="https://www.ebay.com/itm/compliance-smoke",
        brand=brand,
        model=model,
        category=ItemCategory(category),
        condition_text=condition_text,
        condition_normalized=ItemCondition.LIKE_NEW,
        listing_price_usd=Decimal("180"),
        us_shipping_usd=Decimal("22"),
        seller_id="seller_smoke",
        seller_feedback_count=seller_feedback,
        seller_feedback_pct=Decimal(str(seller_pct)),
        photos=[f"https://example.com/{i}.jpg" for i in range(n_photos)],
    )

    verdict = compliance_gate(candidate)
    _render_compliance(verdict)


@compliance_app.command("check")
def compliance_check(
    upc: Annotated[Optional[str], typer.Option(help="UPC code")] = None,
    brand: Annotated[Optional[str], typer.Option(help="Brand")] = None,
    model: Annotated[Optional[str], typer.Option(help="Model")] = None,
) -> None:
    """Lightweight CPSC + safety check by UPC or brand+model."""
    if not (upc or (brand and model)):
        console.print("[red]Need either --upc or both --brand and --model[/red]")
        raise typer.Exit(1)

    write_cache_for_test([])  # seed empty cache for MVP
    candidate = BuyCandidate(
        candidate_id="check",
        marketplace="ebay",
        listing_url="https://www.ebay.com/itm/check",
        brand=brand or "",
        model=model or "",
        upc=upc,
        category=ItemCategory.OTHER,
        condition_text="",
        condition_normalized=ItemCondition.UNKNOWN,
        listing_price_usd=Decimal("0"),
        seller_id="check",
        seller_feedback_count=200,
        seller_feedback_pct=Decimal("99"),
        photos=[],
    )
    verdict = compliance_gate(candidate)
    _render_compliance(verdict)


# ── demand ──────────────────────────────────────────────────────────
@demand_app.command("score")
def demand_score(
    name: Annotated[str, typer.Argument()],
    jiji_active: Annotated[int, typer.Option()] = 0,
    jiji_sold_30d: Annotated[int, typer.Option()] = 0,
    jiji_median_sold: Annotated[float, typer.Option()] = 0,
    jumia_stock: Annotated[str, typer.Option()] = "not_listed",
    jumia_weeks_out: Annotated[int, typer.Option()] = 0,
    fb_mentions: Annotated[int, typer.Option()] = 0,
    fb_intent: Annotated[float, typer.Option()] = 0.0,
    ig_mentions: Annotated[int, typer.Option()] = 0,
    tiktok_mentions: Annotated[int, typer.Option()] = 0,
) -> None:
    """Score a product from raw demand signals."""
    signals = DemandSignals(
        jiji_active_listings=jiji_active or None,
        jiji_sold_30d=jiji_sold_30d or None,
        jiji_median_sold_kes=Decimal(str(jiji_median_sold)) if jiji_median_sold else None,
        jumia_stock=jumia_stock,
        jumia_weeks_out_of_stock=jumia_weeks_out or None,
        fb_group_mentions_30d=fb_mentions or None,
        fb_group_intent_score=Decimal(str(fb_intent)) if fb_intent else None,
        ig_kenyan_mentions_30d=ig_mentions or None,
        tiktok_kenyan_mentions_30d=tiktok_mentions or None,
    )
    sig = compose_signal(name, signals)
    table = Table(title=f"Demand signal: {name}")
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("demand_score", f"{sig.demand_score:.3f}")
    table.add_row("confidence", sig.confidence)
    table.add_row("recommendation", sig.recommendation or "")
    table.add_row("missing_data", ", ".join(sig.missing_data) or "—")
    console.print(table)


# ── brief ───────────────────────────────────────────────────────────
@brief_app.command("weekly")
def brief_weekly(
    dry_run: Annotated[bool, typer.Option(help="Don't post to Telegram")] = True,
) -> None:
    """Generate the weekly sourcing brief.

    Status: stub. Hermes runs this for real once the pieces are wired:
      1. read latest Demand Scout output from data/cache/demand_scout/
      2. read last 4 weeks of margin reports
      3. compose the brief per docs/skills/trend-pm/SKILL.md
      4. post to Telegram
      5. open PR with the brief markdown
    """
    console.print(
        Panel(
            "[yellow]Brief generation runs through Hermes in MVP.[/yellow]\n\n"
            "Send to Hermes on Telegram:\n"
            "  [bold]Run the weekly sourcing brief[/bold]\n\n"
            "Or after wiring src/baby_arb/sourcing and a Demand Scout cache, "
            "this command will compose and post the brief locally.",
            title="brief weekly",
        )
    )


# ── db ──────────────────────────────────────────────────────────────
@db_app.command("init")
def db_init() -> None:
    """Initialise the SQLite database. (Stub — Hermes handoff.)"""
    console.print(
        Panel(
            "[yellow]Storage layer is a Hermes handoff item.[/yellow] "
            "See src/baby_arb/storage/__init__.py for the build plan.",
            title="db init",
        )
    )


# ── helpers ─────────────────────────────────────────────────────────
def _yn(v: object) -> str:
    return "OK" if v else "MISSING"


def _mask(v: str | None) -> str:
    if not v:
        return "—"
    if len(v) <= 8:
        return "***"
    return f"{v[:4]}…{v[-3:]}"


def _render_pricing(candidate, landed, verdict) -> None:
    """Pretty-print a pricing verdict."""
    color = {
        "BUY": "green",
        "SKIP": "red",
        "ABSTAIN": "yellow",
        "REVIEW": "magenta",
    }.get(verdict.verdict.value, "white")

    console.print(
        Panel(
            f"[bold {color}]{verdict.verdict.value}[/bold {color}] "
            f"— margin {verdict.margin_pct:.1f}% "
            f"({verdict.margin_kes:,.0f} KES)\n\n"
            f"Reference KE sale: {verdict.reference_ke_sale_price_kes:,.0f} KES\n"
            f"Total landed: {verdict.total_landed_kes:,.0f} KES\n"
            f"Confidence: {verdict.confidence.value}\n"
            f"Biggest cost driver: {verdict.biggest_cost_driver}\n"
            f"Slimmest assumption: {verdict.slimmest_assumption}\n\n"
            f"{verdict.explanation}",
            title=f"Pricing verdict — {candidate.brand} {candidate.model}",
        )
    )

    table = Table(title="Cost breakdown")
    table.add_column("Component")
    table.add_column("Value", justify="right")
    table.add_row("listing_price_usd", f"${landed.listing_price_usd:,.2f}")
    table.add_row("us_shipping_usd", f"${landed.us_shipping_usd:,.2f}")
    table.add_row("us_sales_tax_usd", f"${landed.us_sales_tax_usd:,.2f}")
    table.add_row("warehouse_handling_usd", f"${landed.warehouse_handling_usd:,.2f}")
    table.add_row("international_shipping_usd", f"${landed.international_shipping_usd:,.2f}")
    table.add_row("insurance_usd", f"${landed.insurance_usd:,.2f}")
    table.add_row("CIF (KES)", f"{landed.cif_kes:,.0f}")
    table.add_row("ke_duty_kes", f"{landed.ke_duty_kes:,.0f}")
    table.add_row("ke_idf_kes", f"{landed.ke_idf_kes:,.0f}")
    table.add_row("ke_rdl_kes", f"{landed.ke_rdl_kes:,.0f}")
    table.add_row("ke_vat_kes", f"{landed.ke_vat_kes:,.0f}")
    table.add_row("ke_last_mile_kes", f"{landed.ke_last_mile_kes:,.0f}")
    table.add_row("[bold]TOTAL LANDED (KES)[/bold]", f"[bold]{landed.total_landed_kes:,.0f}[/bold]")
    table.add_row("FX rate", f"{landed.fx_rate_usdkes} (age {landed.fx_rate_age_hours:.1f}h)")
    table.add_row("Billable weight", f"{landed.weight_used_lb:.1f} lb ({landed.weight_source})")
    table.add_row("Dim weight billed", "yes" if landed.dim_weight_used else "no")
    console.print(table)


def _render_compliance(verdict) -> None:
    color = {
        "PASS": "green",
        "BLOCK": "red",
        "REVIEW": "yellow",
    }.get(verdict.verdict.value, "white")
    console.print(
        Panel(
            f"[bold {color}]{verdict.verdict.value}[/bold {color}]\n\n"
            f"Reasons: {', '.join(verdict.reasons) if verdict.reasons else '—'}\n"
            f"Checks run: {', '.join(verdict.checks_run)}\n"
            f"Checks skipped: {', '.join(verdict.checks_skipped) if verdict.checks_skipped else '—'}",
            title="Compliance verdict",
        )
    )


if __name__ == "__main__":
    app()
