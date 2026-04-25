import hashlib
import html
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Optional
from urllib.parse import quote_plus

import requests

from .models import Deal

FRONTPAGE_RSS = "https://slickdeals.net/rss.php?pageSection=deals-frontpage"
POPULAR_RSS   = "https://slickdeals.net/rss.php?pageSection=deals-popular"
SEARCH_RSS_TEMPLATE = (
    "https://slickdeals.net/newsearch.php"
    "?src=SearchBarV2&q={query}&searcharea=deals&searchin=first_word&rss=1"
)

_PRICE_RE = re.compile(r"\$[\d,]+(?:\.\d{2})?")
_SCORE_RE = re.compile(
    r"Thumb\s+Score:\s*[+-]?(\d+)"           # Slickdeals format: "Thumb Score: +14"
    r"|(\d+)\s*(?:votes?|thumbs?(?:\s+up)?)", # fallback: "14 thumbs up"
    re.IGNORECASE,
)
_STORE_SEP_RE = re.compile(r"\s+(?:at|from|@)\s+", re.IGNORECASE)

# Realistic browser headers — slickdeals blocks obvious bot UAs
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept":          "application/rss+xml, application/xml, text/xml, */*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Cache-Control":   "no-cache",
    "Referer":         "https://slickdeals.net/",
}

# Single session reuses cookies across requests (helps with bot detection)
_session = requests.Session()
_session.headers.update(_HEADERS)

fetch_errors: list[str] = []


def _fetch_rss(url: str) -> list[ET.Element]:
    try:
        resp = _session.get(url, timeout=20)
        resp.raise_for_status()
        ct = resp.headers.get("Content-Type", "")
        if "html" in ct and "xml" not in ct:
            fetch_errors.append(
                f"Slickdeals returned HTML instead of RSS for {url} "
                f"(status {resp.status_code}) — possibly rate-limited or blocked"
            )
            return []
        root = ET.fromstring(resp.content)
        items = root.findall(".//item")
        return items
    except requests.HTTPError as e:
        fetch_errors.append(f"HTTP {e.response.status_code} fetching {url}")
        return []
    except Exception as e:
        fetch_errors.append(f"Error fetching {url}: {e}")
        return []


def fetch_raw_sample(url: str, limit: int = 3) -> list[dict]:
    """Return raw fields from the first N RSS items — used by the debug endpoint."""
    try:
        resp = _session.get(url, timeout=20)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        items = root.findall(".//item")
        out = []
        for item in items[:limit]:
            fields = {child.tag: (child.text or "") for child in item}
            out.append(fields)
        return out
    except Exception as e:
        return [{"error": str(e)}]


def _text(item: ET.Element, tag: str) -> str:
    el = item.find(tag)
    return (el.text or "").strip() if el is not None else ""


def _clean(raw: str) -> str:
    """Strip HTML tags then unescape HTML entities."""
    stripped = re.sub(r"<[^>]+>", "", raw)
    return html.unescape(stripped)


def _extract_price(text: str) -> tuple[Optional[str], Optional[str]]:
    prices = _PRICE_RE.findall(text)
    if len(prices) >= 2:
        return prices[0], prices[1]
    if len(prices) == 1:
        return prices[0], None
    return None, None


def _extract_score(item: ET.Element) -> int:
    """Extract the Thumb Score from an RSS item.

    Slickdeals puts 'Thumb Score: +N' inside the content:encoded HTML field.
    """
    # Concatenate raw text of all child elements, then also strip HTML for a clean pass
    raw = " ".join((child.text or "") for child in item)
    cleaned = _clean(raw)

    for text in (cleaned, raw):
        m = _SCORE_RE.search(text)
        if m:
            val = int(m.group(1) or m.group(2) or 0)
            # Cap at 99999 — larger values are garbled IDs/timestamps from the feed
            return val if val < 100_000 else 0

    return 0


def _extract_store(title: str) -> Optional[str]:
    parts = _STORE_SEP_RE.split(title)
    return parts[-1].strip() if len(parts) > 1 else None


def _parse_date(date_str: str) -> datetime:
    try:
        return parsedate_to_datetime(date_str).astimezone(timezone.utc).replace(tzinfo=None)
    except Exception:
        return datetime.utcnow()


_CONTENT_NS = "{http://purl.org/rss/1.0/modules/content/}encoded"
_IMG_RE = re.compile(r'<img[^>]+src="([^"]+)"', re.IGNORECASE)


def _item_to_deal(item: ET.Element, matched_keywords: list[str]) -> Deal:
    title = _text(item, "title")
    url = _text(item, "link")
    pub_date = _parse_date(_text(item, "pubDate"))

    # content:encoded has the full HTML; description is the short plain-text preview
    content_html = _text(item, _CONTENT_NS)
    short_desc = _text(item, "description")
    summary = _clean(content_html or short_desc)[:300]

    # Extract image from content:encoded <img> tag
    img_match = _IMG_RE.search(content_html)
    image_url = img_match.group(1) if img_match else None

    price, original_price = _extract_price(title + " " + summary)
    score = _extract_score(item)
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
        image_url=image_url,
        matched_keywords=matched_keywords,
    )


def _matches(item: ET.Element, keywords: list[str], exclude: list[str]) -> list[str]:
    title = _text(item, "title").lower()
    desc = _clean(_text(item, "description")).lower()
    text = title + " " + desc

    if any(ex.lower() in text for ex in exclude):
        return []
    # Empty keywords list = match everything
    if not keywords:
        return ["*"]
    return [kw for kw in keywords if kw.lower() in text]


def fetch_hot_deals(min_score: int, exclude: list[str]) -> list[Deal]:
    """Fetch frontpage + popular RSS with no keyword filter."""
    deals: dict[str, Deal] = {}
    raw_count = 0
    for url in [FRONTPAGE_RSS, POPULAR_RSS]:
        items = _fetch_rss(url)
        raw_count += len(items)
        for item in items:
            title = _text(item, "title").lower()
            desc = _clean(_text(item, "description")).lower()
            if any(ex.lower() in (title + " " + desc) for ex in exclude):
                continue
            deal = _item_to_deal(item, ["hot"])
            if deal.score >= min_score and deal.id not in deals:
                deals[deal.id] = deal
    print(f"[hot-deals] {raw_count} raw RSS items → {len(deals)} unique deals "
          f"(min_score={min_score})", flush=True)
    return sorted(deals.values(), key=lambda d: d.score, reverse=True)


def fetch_frontpage(keywords: list[str], exclude: list[str], min_score: int) -> list[Deal]:
    deals: dict[str, Deal] = {}
    raw_count = 0
    for url in [FRONTPAGE_RSS, POPULAR_RSS]:
        items = _fetch_rss(url)
        raw_count += len(items)
        for item in items:
            matched = _matches(item, keywords, exclude)
            if not matched:
                continue
            deal = _item_to_deal(item, matched)
            if deal.score >= min_score and deal.id not in deals:
                deals[deal.id] = deal
    print(f"[frontpage] {raw_count} raw items → {len(deals)} matched "
          f"(keywords={keywords[:3]}, min_score={min_score})", flush=True)
    return list(deals.values())


def fetch_search(
    query: str,
    keywords: list[str],
    exclude: list[str],
    min_score: int,
) -> list[Deal]:
    url = SEARCH_RSS_TEMPLATE.format(query=quote_plus(query))
    items = _fetch_rss(url)
    deals: dict[str, Deal] = {}
    for item in items:
        matched = _matches(item, keywords, exclude)
        if keywords and not matched:
            continue
        if not matched:
            matched = [query]
        deal = _item_to_deal(item, matched)
        if deal.score >= min_score and deal.id not in deals:
            deals[deal.id] = deal
    print(f"[search:{query!r}] {len(items)} raw items → {len(deals)} matched "
          f"(min_score={min_score})", flush=True)
    return list(deals.values())
