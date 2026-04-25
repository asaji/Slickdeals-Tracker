import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

from .notifier import PushoverConfig


@dataclass
class HotDealsConfig:
    enabled: bool = False
    # Minimum community vote score; 0 = frontpage inclusion alone is the signal
    min_score: int = 0
    # Common junk to filter even from hot feeds (e.g. credit card offers)
    exclude: list[str] = field(default_factory=list)
    max_display: int = 10
    # Run full review analysis on each hot deal (slower but richer output)
    run_analysis: bool = True
    # Push Pushover notifications for hot deals (uses main pushover credentials)
    notify: bool = True


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
    retention_days: int = 30
    pushover: PushoverConfig = field(default_factory=PushoverConfig)
    hot_deals: HotDealsConfig = field(default_factory=HotDealsConfig)


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
    # Explicit path > CONFIG_PATH env var > hardcoded default
    resolved = path or os.getenv("CONFIG_PATH", "config.yaml")
    config_path = Path(resolved)

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

    hd = data.get("hot_deals", {}) or {}
    hot_deals = HotDealsConfig(
        enabled=hd.get("enabled", False),
        min_score=hd.get("min_score", 0),
        exclude=hd.get("exclude", []),
        max_display=hd.get("max_display", 10),
        run_analysis=hd.get("run_analysis", True),
        notify=hd.get("notify", True),
    )

    po = data.get("pushover", {}) or {}
    pushover = PushoverConfig(
        enabled=po.get("enabled", False),
        api_token=po.get("api_token", ""),
        user_key=po.get("user_key", ""),
        min_verdict=po.get("min_verdict", "GOOD DEAL"),
        notify_on_run=po.get("notify_on_run", False),
        max_per_check=po.get("max_per_check", 5),
    )

    cfg = AppConfig(
        searches=searches,
        poll_interval_minutes=data.get("poll_interval_minutes", 30),
        db_path=data.get("db_path", "deals.db"),
        max_deals_display=data.get("max_deals_display", 20),
        show_seen=data.get("show_seen", False),
        retention_days=data.get("retention_days", 30),
        pushover=pushover,
        hot_deals=hot_deals,
    )

    # Environment variable overrides (Docker / UnRAID pass these in)
    if os.getenv("DB_PATH"):
        cfg.db_path = os.environ["DB_PATH"]
    if os.getenv("POLL_INTERVAL"):
        cfg.poll_interval_minutes = int(os.environ["POLL_INTERVAL"])
    if os.getenv("PUSHOVER_TOKEN"):
        cfg.pushover.api_token = os.environ["PUSHOVER_TOKEN"]
    if os.getenv("PUSHOVER_USER_KEY"):
        cfg.pushover.user_key = os.environ["PUSHOVER_USER_KEY"]
    if os.getenv("PUSHOVER_ENABLED"):
        cfg.pushover.enabled = os.environ["PUSHOVER_ENABLED"].lower() == "true"
    if os.getenv("HOT_DEALS_ENABLED"):
        cfg.hot_deals.enabled = os.environ["HOT_DEALS_ENABLED"].lower() == "true"
    if os.getenv("HOT_DEALS_MIN_SCORE"):
        cfg.hot_deals.min_score = int(os.environ["HOT_DEALS_MIN_SCORE"])

    return cfg


def write_default_config(path: str = "config.yaml") -> None:
    with open(path, "w") as f:
        yaml.dump(DEFAULT_CONFIG, f, default_flow_style=False, sort_keys=False)


def save_settings(settings: dict, path: str) -> None:
    """Update top-level and pushover settings in the config file."""
    config_path = Path(path)
    if config_path.exists():
        with open(config_path) as f:
            data = yaml.safe_load(f) or {}
    else:
        data = {}

    for key in ("poll_interval_minutes", "retention_days"):
        if key in settings:
            data[key] = int(settings[key])

    pushover_keys = ("min_verdict", "max_per_check", "pushover_enabled", "pushover_token", "pushover_user_key")
    if any(k in settings for k in pushover_keys):
        po = data.setdefault("pushover", {})
        if "min_verdict" in settings:
            po["min_verdict"] = settings["min_verdict"]
        if "max_per_check" in settings:
            po["max_per_check"] = int(settings["max_per_check"])
        if "pushover_enabled" in settings:
            po["enabled"] = bool(settings["pushover_enabled"])
        if settings.get("pushover_token"):
            po["api_token"] = settings["pushover_token"]
        if settings.get("pushover_user_key"):
            po["user_key"] = settings["pushover_user_key"]

    with open(config_path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)


def save_searches(searches: list[SearchConfig], path: str) -> None:
    """Rewrite only the searches list in the config file, preserving all other keys."""
    config_path = Path(path)
    if config_path.exists():
        with open(config_path) as f:
            data = yaml.safe_load(f) or {}
    else:
        data = {}

    data["searches"] = [
        {
            "name": s.name,
            "query": s.query,
            **({"category": s.category} if s.category else {}),
            "keywords": s.keywords,
            "exclude": s.exclude,
            "min_score": s.min_score,
        }
        for s in searches
    ]
    with open(config_path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)
