"""Flask web dashboard for Slickdeals Tracker."""

import os
import subprocess
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from .config import SearchConfig, load_config, save_searches, save_settings
from .database import DealDatabase
from .fetcher import FRONTPAGE_RSS, POPULAR_RSS, SEARCH_RSS_TEMPLATE, fetch_raw_sample

app = Flask(__name__)

_db_path = os.getenv("DB_PATH", "deals.db")
_config_path = os.getenv("CONFIG_PATH", "config.yaml")


def _detect_version() -> str:
    # Explicit env var wins (e.g. set by orchestrator), but skip the "dev" default
    v = os.getenv("APP_VERSION", "").strip()
    if v and v != "dev":
        return v
    # VERSION file baked in at Docker build time
    version_file = Path(os.path.dirname(os.path.abspath(__file__))).parent / "VERSION"
    try:
        v = version_file.read_text().strip()
        if v and v != "dev":
            return v
    except Exception:
        pass
    # Local dev fallback: ask git directly
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=2,
            cwd=os.path.dirname(os.path.abspath(__file__)),
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except Exception:
        pass
    return "dev"


_version = _detect_version()


def _get_db() -> DealDatabase:
    return DealDatabase(_db_path)


def _load_cfg():
    return load_config(_config_path)


# ── Pages ─────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html", version=_version)


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


# ── Deals API ─────────────────────────────────────────────────────────────────

@app.route("/api/deals")
def api_deals():
    db = _get_db()
    deals = db.get_recent_deals(limit=200)
    return jsonify([
        {
            "id": d.id,
            "title": d.title,
            "url": d.url,
            "price": d.price,
            "original_price": d.original_price,
            "score": d.score,
            "category": d.category,
            "category_detected": d.category_detected,
            "store": d.store,
            "published": d.published.isoformat(),
            "image_url": d.image_url,
            "seen": d.seen,
            "matched_keywords": d.matched_keywords,
            "verdict": d.verdict,
            "verdict_color": d.verdict_color,
            "value_score": d.value_score,
            "discount_pct": d.discount_pct,
            "savings_str": d.savings_str,
            "saved": d.saved,
        }
        for d in deals
    ])


@app.route("/api/stats")
def api_stats():
    db = _get_db()
    return jsonify(db.get_stats())


@app.route("/api/mark-seen/<deal_id>", methods=["POST"])
def mark_seen(deal_id: str):
    db = _get_db()
    db.mark_seen(deal_id)
    return jsonify({"ok": True})


@app.route("/api/deals/<path:deal_id>/save", methods=["POST"])
def toggle_save(deal_id: str):
    db = _get_db()
    new_state = db.toggle_saved(deal_id)
    return jsonify({"saved": new_state})


@app.route("/api/settings")
def api_get_settings():
    cfg = _load_cfg()
    return jsonify({
        "poll_interval_minutes": cfg.poll_interval_minutes,
        "retention_days": cfg.retention_days,
        "min_verdict": cfg.pushover.min_verdict,
        "max_per_check": cfg.pushover.max_per_check,
        "pushover_enabled": cfg.pushover.enabled,
        "pushover_token": cfg.pushover.api_token,
        "pushover_user_key": cfg.pushover.user_key,
        "version": _version,
    })


@app.route("/api/settings", methods=["POST"])
def api_save_settings():
    data = request.get_json(force=True) or {}
    allowed = {
        "poll_interval_minutes", "retention_days",
        "min_verdict", "max_per_check",
        "pushover_enabled", "pushover_token", "pushover_user_key",
    }
    filtered = {k: v for k, v in data.items() if k in allowed}
    try:
        save_settings(filtered, _config_path)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Debug ─────────────────────────────────────────────────────────────────────

@app.route("/api/debug/rss")
def api_debug_rss():
    """Return raw fields from the first 3 items of each feed — helps diagnose score extraction."""
    from urllib.parse import quote_plus
    results = {
        "frontpage": fetch_raw_sample(FRONTPAGE_RSS),
        "popular":   fetch_raw_sample(POPULAR_RSS),
    }
    return jsonify(results)


# ── Searches / Alert Rules API ─────────────────────────────────────────────────

@app.route("/api/searches")
def api_searches():
    cfg = _load_cfg()
    return jsonify([
        {
            "name": s.name,
            "query": s.query,
            "category": s.category,
            "keywords": s.keywords,
            "exclude": s.exclude,
            "min_score": s.min_score,
        }
        for s in cfg.searches
    ])


@app.route("/api/searches", methods=["POST"])
def api_add_search():
    data = request.get_json(force=True) or {}
    name = (data.get("name") or "").strip()
    query = (data.get("query") or "").strip()
    if not name or not query:
        return jsonify({"error": "name and query are required"}), 400

    cfg = _load_cfg()
    if any(s.name == name for s in cfg.searches):
        return jsonify({"error": f"Alert '{name}' already exists"}), 409

    def _split(v):
        return [x.strip() for x in (v or "").split(",") if x.strip()]

    cfg.searches.append(SearchConfig(
        name=name,
        query=query,
        category=data.get("category", ""),
        keywords=_split(data.get("keywords", "")),
        exclude=_split(data.get("exclude", "")),
        min_score=int(data.get("min_score") or 0),
    ))
    save_searches(cfg.searches, _config_path)
    return jsonify({"ok": True}), 201


@app.route("/api/searches/<path:name>", methods=["DELETE"])
def api_delete_search(name: str):
    cfg = _load_cfg()
    before = len(cfg.searches)
    cfg.searches = [s for s in cfg.searches if s.name != name]
    if len(cfg.searches) == before:
        return jsonify({"error": "Not found"}), 404
    save_searches(cfg.searches, _config_path)
    return jsonify({"ok": True})


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    from waitress import serve
    port = int(os.getenv("PORT", "7001"))
    print(f"Starting web dashboard on port {port}…", flush=True)
    serve(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
