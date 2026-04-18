#!/usr/bin/env python3
"""Slickdeals deal tracker CLI."""

import time
from pathlib import Path

import click
from rich.console import Console

from slickdeals_tracker.analyzer import analyze_deal
from slickdeals_tracker.config import load_config, write_default_config
from slickdeals_tracker.database import DealDatabase
from slickdeals_tracker.demo import sample_deals, sample_hot_deals
from slickdeals_tracker.display import (
    console,
    print_analysis,
    print_deals_table,
    print_header,
    print_hot_header,
    print_summary,
)
from slickdeals_tracker.fetcher import fetch_errors, fetch_frontpage, fetch_hot_deals, fetch_search
from slickdeals_tracker.notifier import notify_analyses, notify_new_deals, send_test

_console = Console()


# ---------------------------------------------------------------------------
# Core logic helpers
# ---------------------------------------------------------------------------

def _flush_fetch_errors() -> None:
    for err in fetch_errors:
        _console.print(f"[yellow]Warning:[/yellow] {err}")
    fetch_errors.clear()


def _check_hot_deals(cfg, db: DealDatabase) -> list:
    """Fetch hot frontpage deals, save new ones, optionally analyze. Returns analyses or deals."""
    hd = cfg.hot_deals
    print_hot_header()

    deals = fetch_hot_deals(min_score=hd.min_score, exclude=hd.exclude)

    new_deals = []
    for deal in deals:
        if not db.is_seen(deal.id):
            deal.seen = False
            db.save_deal(deal)
            new_deals.append(deal)

    if not new_deals:
        _console.print("[dim]No new hot deals.[/dim]\n")
        return []

    analyses = []
    if hd.run_analysis:
        _console.print(f"[bold]Analyzing {len(new_deals[:hd.max_display])} hot deal(s)…[/bold]\n")
        for deal in new_deals[: hd.max_display]:
            result = analyze_deal(deal, category_hint="")
            print_analysis(result)
            analyses.append(result)
    else:
        print_deals_table(new_deals[: hd.max_display], show_seen=False)

    print_summary(len(new_deals), len(deals))

    if hd.notify and cfg.pushover.enabled:
        if analyses:
            sent = notify_analyses(cfg.pushover, analyses)
        else:
            sent = notify_new_deals(cfg.pushover, new_deals[: hd.max_display], "Hot Deals")
        if sent:
            _console.print(f"[dim]Pushover: sent {sent} hot deal notification(s).[/dim]")

    return analyses or new_deals


def _run_once(cfg, db: DealDatabase) -> tuple[int, int]:
    all_new: int = 0
    all_total: int = 0

    for search in cfg.searches:
        print_header(search.name)

        deals = fetch_search(
            query=search.query,
            keywords=search.keywords,
            exclude=search.exclude,
            min_score=search.min_score,
        )
        frontpage_deals = fetch_frontpage(
            keywords=search.keywords or [search.query],
            exclude=search.exclude,
            min_score=search.min_score,
        )

        seen_ids: set[str] = {d.id for d in deals}
        for d in frontpage_deals:
            if d.id not in seen_ids:
                deals.append(d)
                seen_ids.add(d.id)

        new_deals = []
        for deal in deals:
            if not db.is_seen(deal.id):
                deal.seen = False
                db.save_deal(deal)
                new_deals.append(deal)
            else:
                deal.seen = True
                if cfg.show_seen:
                    new_deals.append(deal)

        print_deals_table(deals[: cfg.max_deals_display], show_seen=cfg.show_seen)
        print_summary(len(new_deals), len(deals))

        if new_deals and cfg.pushover.notify_on_run:
            sent = notify_new_deals(cfg.pushover, new_deals, search.name)
            if sent:
                _console.print(f"[dim]Pushover: sent {sent} notification(s) for {search.name}.[/dim]")

        all_new += len(new_deals)
        all_total += len(deals)

    if cfg.hot_deals.enabled:
        _check_hot_deals(cfg, db)

    _flush_fetch_errors()
    return all_new, all_total


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

@click.group()
def cli() -> None:
    """Slickdeals deal tracker — monitor deals by keyword and category."""


@cli.command()
@click.option("--config", "-c", default="config.yaml", help="Path to config file.")
@click.option("--watch", "-w", is_flag=True, help="Keep running and poll on interval.")
@click.option("--interval", "-i", type=int, default=None, help="Override poll interval (minutes).")
@click.option("--demo", is_flag=True, help="Show sample deals without fetching live data.")
def run(config: str, watch: bool, interval: int, demo: bool) -> None:
    """Fetch and display matching deals."""
    if demo:
        print_header("Demo — Sample TV Deals")
        deals = sample_deals()
        print_deals_table(deals, show_seen=True)
        print_summary(len(deals), len(deals))
        return

    cfg = load_config(config)
    db = DealDatabase(cfg.db_path)
    poll_minutes = interval or cfg.poll_interval_minutes

    if watch:
        _console.print(f"[bold]Watching for deals every {poll_minutes} minute(s). Ctrl+C to stop.[/bold]\n")
        while True:
            _run_once(cfg, db)
            _console.print(f"[dim]Sleeping {poll_minutes}m until next check…[/dim]")
            time.sleep(poll_minutes * 60)
    else:
        _run_once(cfg, db)


@cli.command()
@click.option("--config", "-c", default="config.yaml", help="Path to config file.")
@click.option("--demo", is_flag=True, help="Analyze sample TV deals without network fetch.")
def analyze(config: str, demo: bool) -> None:
    """Fetch deals, score them with review analysis, and push Pushover notifications."""
    if demo:
        deals_with_category = [(d, "TVs") for d in sample_deals()]
        pushover_cfg = None
    else:
        cfg = load_config(config)
        db = DealDatabase(cfg.db_path)
        pushover_cfg = cfg.pushover
        deals_with_category: list[tuple] = []
        seen_ids: set[str] = set()
        for search in cfg.searches:
            fetched = fetch_search(
                query=search.query,
                keywords=search.keywords,
                exclude=search.exclude,
                min_score=search.min_score,
            )
            for d in fetched:
                if d.id not in seen_ids:
                    deals_with_category.append((d, search.category or search.name))
                    seen_ids.add(d.id)
        _flush_fetch_errors()

    if not deals_with_category:
        _console.print("[dim]No deals to analyze.[/dim]")
        return

    _console.print(f"\n[bold]Analyzing {len(deals_with_category)} deal(s) — looking up reviews…[/bold]\n")
    analyses = []
    for deal, category in sorted(deals_with_category, key=lambda x: x[0].score, reverse=True):
        result = analyze_deal(deal, category_hint=category)
        print_analysis(result)
        analyses.append(result)

    if pushover_cfg:
        sent = notify_analyses(pushover_cfg, analyses)
        if sent:
            _console.print(f"[dim]Pushover: sent {sent} notification(s).[/dim]")


@cli.command()
@click.option("--config", "-c", default="config.yaml", help="Path to config file.")
@click.option("--watch", "-w", is_flag=True, help="Keep polling on the configured interval.")
@click.option("--interval", "-i", type=int, default=None, help="Override poll interval (minutes).")
@click.option("--demo", is_flag=True, help="Show sample hot deals without fetching live data.")
def hot(config: str, watch: bool, interval: int, demo: bool) -> None:
    """Show top frontpage deals regardless of category — the truly hot stuff."""
    if demo:
        print_hot_header()
        deals = sample_hot_deals()
        _console.print(f"[bold]Analyzing {len(deals)} hot deal(s) — looking up reviews…[/bold]\n")
        for deal in deals:
            result = analyze_deal(deal, category_hint="")
            print_analysis(result)
        print_summary(len(deals), len(deals))
        return

    cfg = load_config(config)
    db = DealDatabase(cfg.db_path)

    # Temporarily enable hot deals for this command even if disabled in config
    cfg.hot_deals.enabled = True
    poll_minutes = interval or cfg.poll_interval_minutes

    if watch:
        _console.print(f"[bold]Watching for hot deals every {poll_minutes} minute(s). Ctrl+C to stop.[/bold]\n")
        while True:
            _check_hot_deals(cfg, db)
            _flush_fetch_errors()
            _console.print(f"[dim]Sleeping {poll_minutes}m until next check…[/dim]")
            time.sleep(poll_minutes * 60)
    else:
        _check_hot_deals(cfg, db)
        _flush_fetch_errors()


@cli.command()
@click.option("--config", "-c", default="config.yaml", help="Path to config file.")
@click.option("--limit", "-n", default=20, help="Number of recent deals to show.")
def history(config: str, limit: int) -> None:
    """Show recently tracked deals from the database."""
    cfg = load_config(config)
    db = DealDatabase(cfg.db_path)
    deals = db.get_recent_deals(limit)
    print_deals_table(deals, show_seen=True)


@cli.command("notify-test")
@click.option("--config", "-c", default="config.yaml", help="Path to config file.")
def notify_test(config: str) -> None:
    """Send a test Pushover notification to verify your credentials."""
    cfg = load_config(config)
    if not cfg.pushover.enabled:
        _console.print("[yellow]Pushover is disabled in config. Set enabled: true to use it.[/yellow]")
        return
    if not cfg.pushover.api_token or not cfg.pushover.user_key:
        _console.print("[red]api_token and user_key must both be set in the pushover config.[/red]")
        return
    _console.print("Sending test notification…")
    ok = send_test(cfg.pushover)
    if ok:
        _console.print("[green]✓ Test notification sent successfully.[/green]")
    else:
        _console.print("[red]✗ Failed to send — check your api_token and user_key.[/red]")


@cli.command()
@click.option("--output", "-o", default="config.yaml", help="Output path for config file.")
def init(output: str) -> None:
    """Generate a default config.yaml to customise."""
    if Path(output).exists():
        click.confirm(f"{output} already exists. Overwrite?", abort=True)
    write_default_config(output)
    _console.print(f"[green]Config written to {output}[/green]")
    _console.print("Edit it to add your own search terms, then run: [bold]python main.py run[/bold]")


if __name__ == "__main__":
    cli()
