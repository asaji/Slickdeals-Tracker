from datetime import datetime, timezone

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box
from rich.text import Text

from .models import Deal

console = Console()


def _time_ago(dt: datetime) -> str:
    now = datetime.now(tz=timezone.utc)
    delta = now - dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else now - dt
    minutes = int(delta.total_seconds() / 60)
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h ago"
    return f"{hours // 24}d ago"


def print_deal(deal: Deal, new: bool = True) -> None:
    status = "[bold green]NEW[/bold green]" if new else "[dim]SEEN[/dim]"
    score_color = "green" if deal.score >= 20 else "yellow" if deal.score >= 10 else "white"

    title_text = Text(deal.title, style="bold white")
    meta = (
        f"{status}  [{score_color}]+{deal.score} votes[/{score_color}]  "
        f"[cyan]{deal.savings_str}[/cyan]  "
        f"[dim]{_time_ago(deal.published)}[/dim]"
    )
    if deal.store:
        meta += f"  [magenta]{deal.store}[/magenta]"
    if deal.matched_keywords:
        meta += f"  [dim]matched: {', '.join(deal.matched_keywords)}[/dim]"

    panel = Panel(
        f"{title_text}\n{meta}\n[blue underline]{deal.url}[/blue underline]",
        expand=False,
        box=box.ROUNDED,
    )
    console.print(panel)


def print_deals_table(deals: list[Deal], show_seen: bool = False) -> None:
    visible = [d for d in deals if show_seen or not d.seen]
    if not visible:
        console.print("[dim]No new deals found.[/dim]")
        return

    table = Table(
        title=f"Slickdeals Tracker — {len(visible)} deal(s)",
        box=box.ROUNDED,
        show_lines=True,
    )
    table.add_column("Status", style="bold", width=5)
    table.add_column("Score", justify="right", width=7)
    table.add_column("Price", style="cyan", width=14)
    table.add_column("Title", min_width=40)
    table.add_column("Store", style="magenta", width=18)
    table.add_column("Age", width=8)

    for deal in sorted(visible, key=lambda d: d.score, reverse=True):
        status = "[green]NEW[/green]" if not deal.seen else "[dim]seen[/dim]"
        score_color = "green" if deal.score >= 20 else "yellow" if deal.score >= 10 else "white"
        table.add_row(
            status,
            f"[{score_color}]+{deal.score}[/{score_color}]",
            deal.savings_str,
            f"[link={deal.url}]{deal.title}[/link]",
            deal.store or "",
            _time_ago(deal.published),
        )

    console.print(table)


def print_header(search_name: str) -> None:
    console.rule(f"[bold yellow]Slickdeals Tracker — {search_name}[/bold yellow]")


def print_summary(new_count: int, total_count: int) -> None:
    console.print(
        f"\n[bold]Summary:[/bold] {new_count} new deal(s) found "
        f"out of {total_count} fetched.\n"
    )


def print_analysis(analysis) -> None:
    from .analyzer import DealAnalysis
    a: DealAnalysis = analysis

    verdict_colors = {
        "GREAT DEAL": "bold green",
        "GOOD DEAL": "green",
        "FAIR DEAL": "yellow",
        "SKIP": "red",
    }
    color = verdict_colors.get(a.verdict, "white")

    lines = [
        f"[bold white]{a.deal.title}[/bold white]",
        f"[{color}]▶ {a.verdict}[/{color}]  —  {a.verdict_reason}",
        "",
        f"  Price     : [cyan]{a.deal.savings_str}[/cyan]"
        + (f"  [dim]({a.discount_pct:.0f}% off)[/dim]" if a.discount_pct else ""),
        f"  Panel     : {a.panel_type or 'Unknown'}",
        f"  Size      : {a.size_inches}\"" if a.size_inches else "  Size      : Unknown",
        f"  Score     : +{a.deal.score} community votes",
        f"  Value /10 : [bold]{a.value_score}[/bold]",
    ]

    if a.review:
        lines += [
            "",
            f"  [dim]Review sentiment score: {a.review.score_estimate}/10[/dim]",
        ]
        if a.review.rtings_url:
            lines.append(f"  [blue underline]RTINGS: {a.review.rtings_url}[/blue underline]")
        if a.review.expert_verdict and a.review.expert_verdict != "No review data found.":
            snippet = a.review.expert_verdict[:200]
            lines.append(f"\n  [dim italic]\"{snippet}…\"[/dim italic]")

    lines.append(f"\n  [blue underline]{a.deal.url}[/blue underline]")

    console.print(Panel("\n".join(lines), expand=False, box=box.ROUNDED))
    console.print()
