"""TV deal review analyzer — looks up RTINGS scores and expert reviews via search."""

import re
import time
from dataclasses import dataclass, field
from typing import Optional

import requests

from .models import Deal

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; SlickdealsTracker/1.0)"}

# Regex to extract TV model tokens from a deal title
_BRAND_RE = re.compile(
    r"\b(lg|samsung|sony|tcl|hisense|vizio|philips|panasonic|sharp|insignia|toshiba)\b",
    re.IGNORECASE,
)
_MODEL_RE = re.compile(
    r"\b([A-Z]{1,5}\d{1,5}[A-Z0-9]{0,6}|[A-Z]\d[A-Z]\d+[A-Z0-9]*)\b"
)
_SIZE_RE = re.compile(r"\b(55|60|65|70|75|77|80|83|85|86|98)[\s\"-]?(?:inch|\"|\s*class)?\b", re.IGNORECASE)


@dataclass
class ReviewResult:
    model_guess: str
    rtings_url: Optional[str]
    expert_verdict: str
    score_estimate: Optional[float]  # 0-10
    pros: list[str] = field(default_factory=list)
    cons: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)


@dataclass
class DealAnalysis:
    deal: Deal
    discount_pct: Optional[float]
    panel_type: Optional[str]
    size_inches: Optional[int]
    review: Optional[ReviewResult]
    verdict: str       # "GREAT" / "GOOD" / "FAIR" / "SKIP"
    verdict_reason: str
    value_score: float  # 0-10 composite


def _guess_panel_type(title: str) -> Optional[str]:
    t = title.upper()
    if "OLED" in t:
        return "OLED"
    if "MINI-LED" in t or "MINI LED" in t or "MINILED" in t or "QLED" in t:
        return "Mini-LED/QLED"
    if "QLED" in t:
        return "QLED"
    if "LED" in t or "LCD" in t:
        return "LED/LCD"
    return None


def _extract_size(title: str) -> Optional[int]:
    m = _SIZE_RE.search(title)
    return int(m.group(1)) if m else None


def _discount_pct(price_str: Optional[str], orig_str: Optional[str]) -> Optional[float]:
    if not price_str or not orig_str:
        return None
    try:
        price = float(re.sub(r"[^\d.]", "", price_str))
        orig = float(re.sub(r"[^\d.]", "", orig_str))
        if orig > 0 and price < orig:
            return round((orig - price) / orig * 100, 1)
    except ValueError:
        pass
    return None


def _extract_model_name(title: str) -> str:
    brand = _BRAND_RE.search(title)
    brand_str = brand.group(0).upper() if brand else ""
    models = _MODEL_RE.findall(title)
    model_str = " ".join(models[:2]) if models else ""
    size = _extract_size(title)
    size_str = f'{size}"' if size else ""
    return f"{brand_str} {size_str} {model_str}".strip()


def _ddg_search(query: str) -> list[dict]:
    """Query DuckDuckGo Instant Answers API (no auth, no rate limit blocking)."""
    try:
        resp = requests.get(
            "https://api.duckduckgo.com/",
            params={"q": query, "format": "json", "no_redirect": "1", "no_html": "1"},
            headers=_HEADERS,
            timeout=10,
        )
        data = resp.json()
        results = []
        if data.get("AbstractText"):
            results.append({"text": data["AbstractText"], "url": data.get("AbstractURL", "")})
        for item in data.get("RelatedTopics", [])[:5]:
            if isinstance(item, dict) and item.get("Text"):
                results.append({"text": item["Text"], "url": item.get("FirstURL", "")})
        return results
    except Exception:
        return []


_POSITIVE_WORDS = {"excellent", "great", "outstanding", "impressive", "best", "top", "recommended",
                   "value", "bright", "stunning", "award", "winner", "punches above", "fantastic"}
_NEGATIVE_WORDS = {"disappointing", "dim", "blooming", "poor", "weak", "mediocre", "skip",
                   "avoid", "washed", "ghosting", "banding", "issues", "problems"}


def _sentiment_score(texts: list[str]) -> float:
    combined = " ".join(texts).lower()
    pos = sum(1 for w in _POSITIVE_WORDS if w in combined)
    neg = sum(1 for w in _NEGATIVE_WORDS if w in combined)
    total = pos + neg
    if total == 0:
        return 6.5  # neutral
    return round(5.0 + (pos - neg) / total * 3.5, 1)


def _verdict(value_score: float, discount_pct: Optional[float]) -> tuple[str, str]:
    discount = discount_pct or 0
    if value_score >= 8.0 and discount >= 25:
        return "GREAT DEAL", "Top-reviewed TV at a substantial discount."
    if value_score >= 7.0 and discount >= 15:
        return "GOOD DEAL", "Well-reviewed TV with a solid discount."
    if value_score >= 6.0 or discount >= 20:
        return "FAIR DEAL", "Decent value but not exceptional."
    return "SKIP", "Low review sentiment or minimal discount — wait for better pricing."


def analyze_deal(deal: Deal, delay: float = 1.0) -> DealAnalysis:
    model_name = _extract_model_name(deal.title)
    panel = _guess_panel_type(deal.title)
    size = _extract_size(deal.title)
    discount = _discount_pct(deal.price, deal.original_price)

    # Search for review data
    query = f"{model_name} RTINGS review score"
    time.sleep(delay)  # be polite
    results = _ddg_search(query)

    texts = [r["text"] for r in results]
    rtings_url = next(
        (r["url"] for r in results if "rtings.com" in r.get("url", "")), None
    )

    sentiment = _sentiment_score(texts)

    # Weight: review sentiment (60%) + discount generosity (40%)
    discount_score = min((discount or 0) / 40 * 10, 10)
    value_score = round(sentiment * 0.6 + discount_score * 0.4, 1)

    verdict_label, verdict_reason = _verdict(value_score, discount)

    review = ReviewResult(
        model_guess=model_name,
        rtings_url=rtings_url,
        expert_verdict=" ".join(texts[:2])[:300] if texts else "No review data found.",
        score_estimate=sentiment,
        sources=[r["url"] for r in results if r.get("url")][:3],
    )

    return DealAnalysis(
        deal=deal,
        discount_pct=discount,
        panel_type=panel,
        size_inches=size,
        review=review,
        verdict=verdict_label,
        verdict_reason=verdict_reason,
        value_score=value_score,
    )
