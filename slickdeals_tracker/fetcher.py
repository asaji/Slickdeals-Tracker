import hashlib
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Optional
from urllib.parse import quote_plus

import requests

from .models import Deal

FRONTPAGE_RSS = "https://slickdeals.net/rss.php?pageSection=deals-frontpage"
POPULAR_RSS = "https://slickdeals.net/rss.php?pageSection=deals-popular"
SEARCH_RSS_TEMPLATE = (
    "https://slickdeals.net/newsearch.php"
    "?src=SearchBarV2&q={query}&searcharea=deals&searchin=first_word&rss=1"
)

_PRICE_RE = re.compile(r"\$[\d,]+(?:\.\d{2})?")
_SCORE_RE = re.compile(r"(\d+)\s*(?:votes?|thumbs)", re.IGNORECASE)
_STORE_SEP_RE = re.compile(r"\s+(?:at|from|@)\s+", re.IGNORECASE)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; SlickdealsTracker/1.0)"
}

fetch_errors: list[str] = []


def _fetch_rss(url: str) -> list[ET.Element]:
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=15)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        return root.findall(".//item")
    except requests.HTTPError as e:
        fetch_errors.append(f"HTTP {e.response.status_code} fetching {url}")
        return []
    except Exception as e:
        fetch_errors.append(f"Error fetching {url}: {e}")
        return []


def _text(item: ET.Element, tag: str) -> str:
    el = item.find(tag)
    return (el.text or "").strip() if el is not None else ""


def _extract_price(text: str) -> tuple[Optional[str], Optional[str]]:
    prices = _PRICE_RE.findall(text)
    if len(prices) >= 2:
        return prices[0], prices[1]
    if len(prices) == 1:
        return prices[0], None
    return None, None


def _extract_score(text: str) -> int:
    m = _SCORE_RE.search(text)
    return int(m.group(1)) if m else 0


def _extract_store(title: str) -> Optional[str]:
    parts = _STORE_SEP_RE.split(title)
    return parts[-1].strip() if len(parts) > 1 else None


def _parse_date(date_str: str) -> datetime:
    try:
        return parsedate_to_datetime(date_str).astimezone(timezone.utc).replace(tzinfo=None)
    except Exception:
        return datetime.utcnow()


def _item_to_deal(item: ET.Element, matched_keywords: list[str]) -> Deal:
    title = _text(item, "title")
    url = _text(item, "link")
    pub_date = _parse_date(_text(item, "pubDate"))
    summary = re.sub(r"<[^>]+>", "", _text(item, "description"))[:300]

    price, original_price = _extract_price(title + " " + summary)
    score = _extract_score(summary)
    store = _extract_store(title)
    deal_id = hashlib.md5((url or title).encode()).hexdigest()

    return Deal(
        id=deal_id,
        title=title,
        url=url,
        price=price,
        original_price=original_price,
        score=score,
        category=None,
        store=store,
        published=pub_date,
        summary=summary,
        matched_keywords=matched_keywords,
    )


def _matches(item: ET.Element, keywords: list[str], exclude: list[str]) -> list[str]:
    title = _text(item, "title").lower()
    desc = re.sub(r"<[^>]+>", "", _text(item, "description")).lower()
    text = title + " " + desc

    if any(ex.lower() in text for ex in exclude):
        return []
    return [kw for kw in keywords if kw.lower() in text]


def fetch_frontpage(keywords: list[str], exclude: list[str], min_score: int) -> list[Deal]:
    deals: dict[str, Deal] = {}
    for url in [FRONTPAGE_RSS, POPULAR_RSS]:
        for item in _fetch_rss(url):
            matched = _matches(item, keywords, exclude)
            if not matched:
                continue
            deal = _item_to_deal(item, matched)
            if deal.score >= min_score and deal.id not in deals:
                deals[deal.id] = deal
    return list(deals.values())


def fetch_search(
    query: str,
    keywords: list[str],
    exclude: list[str],
    min_score: int,
) -> list[Deal]:
    url = SEARCH_RSS_TEMPLATE.format(query=quote_plus(query))
    deals: dict[str, Deal] = {}
    for item in _fetch_rss(url):
        matched = _matches(item, keywords, exclude) or [query]
        title_lower = _text(item, "title").lower()
        if any(ex.lower() in title_lower for ex in exclude):
            continue
        deal = _item_to_deal(item, matched)
        if deal.score >= min_score and deal.id not in deals:
            deals[deal.id] = deal
    return list(deals.values())
