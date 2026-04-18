"""Pushover push notification support."""

from dataclasses import dataclass
from typing import Optional

import requests

from .analyzer import DealAnalysis
from .models import Deal

_PUSHOVER_URL = "https://api.pushover.net/1/messages.json"

# Pushover priority levels
_PRIORITY = {
    "GREAT DEAL": 1,   # high — bypasses quiet hours
    "GOOD DEAL":  0,   # normal
    "FAIR DEAL":  -1,  # low — no sound/vibration
    "SKIP":       -2,  # lowest — silent, no notification banner
}

_VERDICT_EMOJI = {
    "GREAT DEAL": "🔥",
    "GOOD DEAL":  "✅",
    "FAIR DEAL":  "🟡",
    "SKIP":       "⏭",
}

_VERDICT_ORDER = ["GREAT DEAL", "GOOD DEAL", "FAIR DEAL", "SKIP"]


@dataclass
class PushoverConfig:
    enabled: bool = False
    api_token: str = ""
    user_key: str = ""
    min_verdict: str = "GOOD DEAL"   # only notify at this level or better
    notify_on_run: bool = False       # send basic notifications from `run` (no analysis)
    max_per_check: int = 5           # cap per poll cycle


def _verdict_gte(verdict: str, minimum: str) -> bool:
    """Return True if verdict is at least as good as minimum."""
    order = _VERDICT_ORDER
    try:
        return order.index(verdict) <= order.index(minimum)
    except ValueError:
        return False


def _build_analysis_message(analysis: DealAnalysis) -> tuple[str, str, str]:
    """Return (title, message, url) for a fully-analyzed deal."""
    emoji = _VERDICT_EMOJI.get(analysis.verdict, "")
    title = f"{emoji} {analysis.verdict} — {analysis.category}"

    lines = [analysis.deal.title]
    price_line = analysis.deal.savings_str
    if analysis.discount_pct:
        price_line += f" · {analysis.discount_pct:.0f}% off"
    if analysis.deal.store:
        price_line += f" · {analysis.deal.store}"
    lines.append(price_line)

    if analysis.specs:
        spec_str = " · ".join(f"{k}: {v}" for k, v in analysis.specs.items())
        lines.append(spec_str)

    lines.append(f"+{analysis.deal.score} votes · Value: {analysis.value_score}/10")

    return title, "\n".join(lines), analysis.deal.url


def _build_deal_message(deal: Deal, search_name: str) -> tuple[str, str, str]:
    """Return (title, message, url) for a basic (non-analyzed) new deal."""
    title = f"🛍 New Deal — {search_name}"
    lines = [
        deal.title,
        deal.savings_str + (f" · {deal.store}" if deal.store else ""),
        f"+{deal.score} votes",
    ]
    return title, "\n".join(lines), deal.url


def send(
    config: PushoverConfig,
    title: str,
    message: str,
    url: str = "",
    priority: int = 0,
) -> bool:
    """Send a single Pushover notification. Returns True on success."""
    if not config.enabled or not config.api_token or not config.user_key:
        return False

    payload: dict = {
        "token":   config.api_token,
        "user":    config.user_key,
        "title":   title[:250],
        "message": message[:1024],
        "priority": priority,
    }
    if url:
        payload["url"] = url
        payload["url_title"] = "View Deal on Slickdeals"

    # Emergency priority requires retry/expire params
    if priority == 2:
        payload["retry"]  = 60
        payload["expire"] = 3600

    try:
        resp = requests.post(_PUSHOVER_URL, data=payload, timeout=10)
        return resp.status_code == 200
    except Exception:
        return False


def notify_analyses(
    config: PushoverConfig,
    analyses: list[DealAnalysis],
) -> int:
    """Send notifications for analyses meeting the min_verdict threshold. Returns count sent."""
    if not config.enabled:
        return 0

    sent = 0
    for analysis in analyses:
        if sent >= config.max_per_check:
            break
        if not _verdict_gte(analysis.verdict, config.min_verdict):
            continue
        title, message, url = _build_analysis_message(analysis)
        priority = _PRIORITY.get(analysis.verdict, 0)
        if send(config, title, message, url, priority):
            sent += 1

    return sent


def notify_new_deals(
    config: PushoverConfig,
    deals: list[Deal],
    search_name: str,
) -> int:
    """Send basic (no analysis) notifications for new deals. Returns count sent."""
    if not config.enabled or not config.notify_on_run:
        return 0

    sent = 0
    for deal in deals:
        if sent >= config.max_per_check:
            break
        title, message, url = _build_deal_message(deal, search_name)
        if send(config, title, message, url, priority=0):
            sent += 1

    return sent


def send_test(config: PushoverConfig) -> bool:
    """Send a test notification to verify credentials."""
    return send(
        config,
        title="Slickdeals Tracker — Test",
        message="Your Pushover notifications are configured correctly.",
        priority=0,
    )
