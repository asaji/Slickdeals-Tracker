from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Deal:
    id: str
    title: str
    url: str
    price: Optional[str]
    original_price: Optional[str]
    score: int
    category: Optional[str]
    store: Optional[str]
    published: datetime
    summary: str
    image_url: Optional[str] = None
    seen: bool = False
    matched_keywords: list[str] = field(default_factory=list)
    # Populated after running analyze
    verdict: Optional[str] = None
    value_score: Optional[float] = None
    category_detected: Optional[str] = None
    discount_pct: Optional[float] = None

    @property
    def savings_str(self) -> str:
        if self.price and self.original_price:
            return f"{self.price} (was {self.original_price})"
        return self.price or "N/A"

    @property
    def verdict_color(self) -> str:
        return {
            "GREAT DEAL": "#22c55e",
            "GOOD DEAL":  "#86efac",
            "FAIR DEAL":  "#fbbf24",
            "SKIP":       "#f87171",
        }.get(self.verdict or "", "#6b7280")
