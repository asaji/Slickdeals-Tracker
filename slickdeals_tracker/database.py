import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator, Optional

from .models import Deal


class DealDatabase:
    def __init__(self, db_path: str = "deals.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _conn(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS deals (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL,
                    price TEXT,
                    original_price TEXT,
                    score INTEGER DEFAULT 0,
                    category TEXT,
                    store TEXT,
                    published TEXT,
                    summary TEXT,
                    image_url TEXT,
                    seen INTEGER DEFAULT 0,
                    saved INTEGER DEFAULT 0,
                    matched_keywords TEXT DEFAULT '',
                    created_at TEXT DEFAULT (datetime('now')),
                    verdict TEXT,
                    value_score REAL,
                    category_detected TEXT,
                    discount_pct REAL
                )
            """)
            # Migrate older databases that pre-date these columns
            existing = {r[1] for r in conn.execute("PRAGMA table_info(deals)").fetchall()}
            for col, typedef in [
                ("verdict",            "TEXT"),
                ("value_score",        "REAL"),
                ("category_detected",  "TEXT"),
                ("discount_pct",       "REAL"),
                ("saved",              "INTEGER DEFAULT 0"),
            ]:
                if col not in existing:
                    conn.execute(f"ALTER TABLE deals ADD COLUMN {col} {typedef}")

    def is_seen(self, deal_id: str) -> bool:
        with self._conn() as conn:
            row = conn.execute("SELECT id FROM deals WHERE id = ?", (deal_id,)).fetchone()
            return row is not None

    def save_deal(self, deal: Deal) -> None:
        with self._conn() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO deals
                    (id, title, url, price, original_price, score, category, store,
                     published, summary, image_url, seen, saved, matched_keywords,
                     verdict, value_score, category_detected, discount_pct)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                deal.id, deal.title, deal.url, deal.price, deal.original_price,
                deal.score, deal.category, deal.store,
                deal.published.isoformat(), deal.summary, deal.image_url,
                int(deal.seen), int(deal.saved), ",".join(deal.matched_keywords),
                deal.verdict, deal.value_score, deal.category_detected, deal.discount_pct,
            ))

    def save_analysis(self, deal_id: str, verdict: str, value_score: float,
                      category_detected: str, discount_pct: Optional[float]) -> None:
        """Update a saved deal with analysis results."""
        with self._conn() as conn:
            conn.execute("""
                UPDATE deals
                SET verdict = ?, value_score = ?, category_detected = ?, discount_pct = ?
                WHERE id = ?
            """, (verdict, value_score, category_detected, discount_pct, deal_id))

    def get_recent_deals(self, limit: int = 50) -> list[Deal]:
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT * FROM deals ORDER BY created_at DESC LIMIT ?
            """, (limit,)).fetchall()
        return [self._row_to_deal(r) for r in rows]

    def get_stats(self) -> dict:
        with self._conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM deals").fetchone()[0]
            new_today = conn.execute(
                "SELECT COUNT(*) FROM deals WHERE date(created_at) = date('now')"
            ).fetchone()[0]
            great = conn.execute(
                "SELECT COUNT(*) FROM deals WHERE verdict = 'GREAT DEAL'"
            ).fetchone()[0]
            good = conn.execute(
                "SELECT COUNT(*) FROM deals WHERE verdict = 'GOOD DEAL'"
            ).fetchone()[0]
            categories = conn.execute("""
                SELECT COALESCE(category_detected, category, 'Unknown') as cat, COUNT(*) as n
                FROM deals GROUP BY cat ORDER BY n DESC LIMIT 10
            """).fetchall()
        return {
            "total": total,
            "new_today": new_today,
            "great_deals": great,
            "good_deals": good,
            "categories": [{"name": r["cat"], "count": r["n"]} for r in categories],
        }

    def mark_seen(self, deal_id: str) -> None:
        with self._conn() as conn:
            conn.execute("UPDATE deals SET seen = 1 WHERE id = ?", (deal_id,))

    def toggle_saved(self, deal_id: str) -> bool:
        """Toggle saved state. Returns the new state."""
        with self._conn() as conn:
            row = conn.execute("SELECT saved FROM deals WHERE id = ?", (deal_id,)).fetchone()
            if not row:
                return False
            new_val = 0 if row["saved"] else 1
            conn.execute("UPDATE deals SET saved = ? WHERE id = ?", (new_val, deal_id))
            return bool(new_val)

    def delete_old_deals(self, days: int) -> int:
        """Delete unsaved deals older than `days`. Returns count deleted."""
        if days <= 0:
            return 0
        with self._conn() as conn:
            result = conn.execute("""
                DELETE FROM deals
                WHERE saved = 0
                  AND datetime(created_at) < datetime('now', ?)
            """, (f"-{days} days",))
            return result.rowcount

    @staticmethod
    def _row_to_deal(row: sqlite3.Row) -> Deal:
        keys = row.keys()
        return Deal(
            id=row["id"],
            title=row["title"],
            url=row["url"],
            price=row["price"],
            original_price=row["original_price"],
            score=row["score"],
            category=row["category"],
            store=row["store"],
            published=datetime.fromisoformat(row["published"]),
            summary=row["summary"],
            image_url=row["image_url"],
            seen=bool(row["seen"]),
            saved=bool(row["saved"]) if "saved" in keys else False,
            matched_keywords=row["matched_keywords"].split(",") if row["matched_keywords"] else [],
            verdict=row["verdict"] if "verdict" in keys else None,
            value_score=row["value_score"] if "value_score" in keys else None,
            category_detected=row["category_detected"] if "category_detected" in keys else None,
            discount_pct=row["discount_pct"] if "discount_pct" in keys else None,
        )
