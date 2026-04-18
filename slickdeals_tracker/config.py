from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

from .notifier import PushoverConfig


@dataclass
class SearchConfig:
    name: str
    query: str
    category: str = ""              # maps to a CategoryProfile key; auto-detected if blank
    keywords: list[str] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)
    min_score: int = 0


@dataclass
class AppConfig:
    searches: list[SearchConfig]
    poll_interval_minutes: int = 30
    db_path: str = "deals.db"
    max_deals_display: int = 20
    show_seen: bool = False
    pushover: PushoverConfig = field(default_factory=PushoverConfig)


DEFAULT_CONFIG: dict = {
    "poll_interval_minutes": 30,
    "db_path": "deals.db",
    "max_deals_display": 20,
    "show_seen": False,
    "searches": [
        {
            "name": "TVs",
            "query": "TV",
            "keywords": ["tv", "television", "oled", "qled", "4k", "8k", "uhd", "hdtv", "smart tv"],
            "exclude": ["monitor", "projector", "streaming stick"],
            "min_score": 10,
        },
        {
            "name": "Laptops",
            "query": "laptop",
            "keywords": ["laptop", "notebook", "chromebook", "macbook", "thinkpad"],
            "exclude": ["case", "bag", "sleeve", "stand"],
            "min_score": 10,
        },
    ],
}


def load_config(path: Optional[str] = None) -> AppConfig:
    config_path = Path(path) if path else Path("config.yaml")

    if config_path.exists():
        with open(config_path) as f:
            data = yaml.safe_load(f) or {}
    else:
        data = DEFAULT_CONFIG

    searches = [
        SearchConfig(
            name=s["name"],
            query=s["query"],
            category=s.get("category", ""),
            keywords=s.get("keywords", []),
            exclude=s.get("exclude", []),
            min_score=s.get("min_score", 0),
        )
        for s in data.get("searches", [])
    ]

    po = data.get("pushover", {}) or {}
    pushover = PushoverConfig(
        enabled=po.get("enabled", False),
        api_token=po.get("api_token", ""),
        user_key=po.get("user_key", ""),
        min_verdict=po.get("min_verdict", "GOOD DEAL"),
        notify_on_run=po.get("notify_on_run", False),
        max_per_check=po.get("max_per_check", 5),
    )

    return AppConfig(
        searches=searches,
        poll_interval_minutes=data.get("poll_interval_minutes", 30),
        db_path=data.get("db_path", "deals.db"),
        max_deals_display=data.get("max_deals_display", 20),
        show_seen=data.get("show_seen", False),
        pushover=pushover,
    )


def write_default_config(path: str = "config.yaml") -> None:
    with open(path, "w") as f:
        yaml.dump(DEFAULT_CONFIG, f, default_flow_style=False, sort_keys=False)
