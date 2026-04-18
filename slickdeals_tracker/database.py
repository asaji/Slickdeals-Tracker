import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from .models import Deal


class DealDatabase:
    def __init__(self, db_path: str = "deals.db"):
        self.db_path = Path(db_path)
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
                    matched_keywords TEXT DEFAULT '',
                    created_at TEXT DEFAULT (datetime('now'))
                )
            """)

    def is_seen(self, deal_id: str) -> bool:
        with self._conn() as conn:
            row = conn.execute("SELECT id FROM deals WHERE id = ?", (deal_id,)).fetchone()
            return row is not None

    def save_deal(self, deal: Deal) -> None:
        with self._conn() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO deals
                    (id, title, url, price, original_price, score, category, store,
                     published, summary, image_url, seen, matched_keywords)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                deal.id, deal.title, deal.url, deal.price, deal.original_price,
                deal.score, deal.category, deal.store,
                deal.published.isoformat(), deal.summary, deal.image_url,
                int(deal.seen), ",".join(deal.matched_keywords),
            ))

    def get_recent_deals(self, limit: int = 50) -> list[Deal]:
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT * FROM deals ORDER BY published DESC LIMIT ?
            """, (limit,)).fetchall()
        return [self._row_to_deal(r) for r in rows]

    def mark_seen(self, deal_id: str) -> None:
        with self._conn() as conn:
            conn.execute("UPDATE deals SET seen = 1 WHERE id = ?", (deal_id,))

    @staticmethod
    def _row_to_deal(row: sqlite3.Row) -> Deal:
        from datetime import datetime
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
            matched_keywords=row["matched_keywords"].split(",") if row["matched_keywords"] else [],
        )
