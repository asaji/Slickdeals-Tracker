"""Flask web dashboard for Slickdeals Tracker."""

import os
from pathlib import Path

from flask import Flask, jsonify, render_template

from .database import DealDatabase

app = Flask(__name__)

_db_path = os.getenv("DB_PATH", "deals.db")
_config_path = os.getenv("CONFIG_PATH", "config.yaml")


def _get_db() -> DealDatabase:
    return DealDatabase(_db_path)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


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


def main():
    from waitress import serve
    port = int(os.getenv("PORT", "7001"))
    print(f"Starting web dashboard on port {port}…", flush=True)
    serve(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
