"""Deal review analyzer — category-aware, works for TVs, laptops, headphones, GPUs, and more."""

import re
import time
from dataclasses import dataclass, field
from typing import Optional

import requests

from .categories import CATEGORIES, CategoryProfile, detect_category
from .models import Deal

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; SlickdealsTracker/1.0)"}

_PRICE_RE = re.compile(r"[^\d.]")


@dataclass
class ReviewResult:
    model_guess: str
    review_site: str
    review_url: Optional[str]
    expert_verdict: str
    score_estimate: Optional[float]  # 0-10 sentiment score
    sources: list[str] = field(default_factory=list)


@dataclass
class DealAnalysis:
    deal: Deal
    category: str
    discount_pct: Optional[float]
    specs: dict[str, str]           # e.g. {"Panel": "OLED", "Size": "65\"", "RAM": "16 GB"}
    review: Optional[ReviewResult]
    verdict: str                    # "GREAT DEAL" / "GOOD DEAL" / "FAIR DEAL" / "SKIP"
    verdict_reason: str
    value_score: float              # 0-10 composite


def _discount_pct(price_str: Optional[str], orig_str: Optional[str]) -> Optional[float]:
    if not price_str or not orig_str:
        return None
    try:
        price = float(_PRICE_RE.sub("", price_str))
        orig  = float(_PRICE_RE.sub("", orig_str))
        if orig > 0 and price < orig:
            return round((orig - price) / orig * 100, 1)
    except ValueError:
        pass
    return None


def _extract_model(title: str, profile: CategoryProfile) -> str:
    """Pull brand + model number tokens from the title using the category's brand list."""
    brand_pat = re.compile(
        r"\b(" + "|".join(re.escape(b) for b in profile.brands) + r")\b",
        re.IGNORECASE,
    ) if profile.brands else None

    model_pat = re.compile(r"\b([A-Z]{1,5}\d{1,5}[A-Z0-9]{0,8}|[A-Z]\d[A-Z]\d+[A-Z0-9]*)\b")

    brand_str = ""
    if brand_pat:
        m = brand_pat.search(title)
        if m:
            brand_str = m.group(0).upper()

    models = model_pat.findall(title)
    model_str = " ".join(models[:2]) if models else ""

    return (brand_str + " " + model_str).strip() or title[:50]


def _ddg_search(query: str) -> list[dict]:
    """DuckDuckGo Instant Answers — no API key, no auth required."""
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
        for item in data.get("RelatedTopics", [])[:6]:
            if isinstance(item, dict) and item.get("Text"):
                results.append({"text": item["Text"], "url": item.get("FirstURL", "")})
        return results
    except Exception:
        return []


def _sentiment(texts: list[str], profile: CategoryProfile) -> float:
    combined = " ".join(texts).lower()
    pos = sum(1 for w in profile.positive_words if w in combined)
    neg = sum(1 for w in profile.negative_words if w in combined)
    total = pos + neg
    if total == 0:
        return 6.5  # neutral default
    return round(5.0 + (pos - neg) / total * 3.5, 1)


def _find_review_url(results: list[dict], profile: CategoryProfile) -> Optional[str]:
    """Look for a URL matching the profile's review site domain."""
    site_domain_hints = {
        "RTINGS":                   "rtings.com",
        "NotebookCheck":            "notebookcheck.net",
        "GSMArena":                 "gsmarena.com",
        "Tom's Hardware":           "tomshardware.com",
        "Tom's Hardware / PCMag":   "tomshardware.com",
        "Tom's Hardware / SmallNetBuilder": "tomshardware.com",
        "DPReview":                 "dpreview.com",
        "Metacritic / IGN":         "metacritic.com",
        "The Verge / PCMag":        "theverge.com",
        "Wirecutter / Consumer Reports": "nytimes.com/wirecutter",
        "Google / PCMag":           "pcmag.com",
    }
    domain = site_domain_hints.get(profile.review_site, "")
    if domain:
        for r in results:
            if domain.split("/")[0] in r.get("url", ""):
                return r["url"]
    return next((r["url"] for r in results if r.get("url")), None)


def _verdict(value_score: float, discount_pct: Optional[float]) -> tuple[str, str]:
    d = discount_pct or 0
    if value_score >= 8.0 and d >= 25:
        return "GREAT DEAL", "Highly rated product at a substantial discount."
    if value_score >= 7.0 and d >= 15:
        return "GOOD DEAL", "Well-reviewed product with a solid discount."
    if value_score >= 6.0 or d >= 20:
        return "FAIR DEAL", "Decent value but not an exceptional deal."
    return "SKIP", "Low review sentiment or minimal discount — wait for better pricing."


def analyze_deal(deal: Deal, category_hint: str = "", delay: float = 1.0) -> DealAnalysis:
    profile = detect_category(deal.title, deal.matched_keywords, category_hint)
    model   = _extract_model(deal.title, profile)
    specs   = profile.extract_specs(deal.title)
    discount = _discount_pct(deal.price, deal.original_price)

    query = profile.review_query_template.format(model=model)
    time.sleep(delay)
    results = _ddg_search(query)

    texts      = [r["text"] for r in results]
    sentiment  = _sentiment(texts, profile)
    review_url = _find_review_url(results, profile)

    # Composite score: review sentiment (60%) + discount depth (40%)
    discount_score = min((discount or 0) / 40 * 10, 10)
    value_score    = round(sentiment * 0.6 + discount_score * 0.4, 1)

    verdict_label, verdict_reason = _verdict(value_score, discount)

    review = ReviewResult(
        model_guess=model,
        review_site=profile.review_site,
        review_url=review_url,
        expert_verdict=" ".join(texts[:2])[:300] if texts else "No review data found.",
        score_estimate=sentiment,
        sources=[r["url"] for r in results if r.get("url")][:3],
    )

    return DealAnalysis(
        deal=deal,
        category=profile.name,
        discount_pct=discount,
        specs=specs,
        review=review,
        verdict=verdict_label,
        verdict_reason=verdict_reason,
        value_score=value_score,
    )
