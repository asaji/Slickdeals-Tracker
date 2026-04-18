#!/usr/bin/env python3
"""Slickdeals deal tracker CLI."""

import time
from pathlib import Path

import click
from rich.console import Console

from slickdeals_tracker.config import load_config, write_default_config
from slickdeals_tracker.database import DealDatabase
from slickdeals_tracker.demo import sample_deals
from slickdeals_tracker.display import console, print_deals_table, print_header, print_summary
from slickdeals_tracker.fetcher import fetch_errors, fetch_frontpage, fetch_search

_console = Console()


def _run_once(config, db: DealDatabase) -> tuple[int, int]:
    all_new: int = 0
    all_total: int = 0

    for search in config.searches:
        print_header(search.name)

        # Fetch from both frontpage/popular and targeted search
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

        # Merge, deduplicate
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
                if config.show_seen:
                    new_deals.append(deal)

        print_deals_table(deals[: config.max_deals_display], show_seen=config.show_seen)
        print_summary(len(new_deals), len(deals))

        all_new += len(new_deals)
        all_total += len(deals)

    if fetch_errors:
        for err in fetch_errors:
            _console.print(f"[yellow]Warning:[/yellow] {err}")
        fetch_errors.clear()

    return all_new, all_total


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
@click.option("--limit", "-n", default=20, help="Number of recent deals to show.")
def history(config: str, limit: int) -> None:
    """Show recently tracked deals from the database."""
    cfg = load_config(config)
    db = DealDatabase(cfg.db_path)
    deals = db.get_recent_deals(limit)
    print_deals_table(deals, show_seen=True)


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
