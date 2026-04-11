import sqlite3
import hashlib
import os
import json
from datetime import datetime, timedelta
from contextlib import contextmanager

DB_PATH = os.environ.get("ANALYTICS_DB_PATH", os.path.join(os.path.dirname(__file__), "analytics.db"))
HASH_SALT = os.environ.get("ANALYTICS_SALT", "menuelf-default-salt-change-me")


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                event_type TEXT NOT NULL,
                visitor_hash TEXT NOT NULL,
                path TEXT,
                meta TEXT
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_events_visitor ON events(visitor_hash)")


def hash_visitor(ip: str, date_str: str) -> str:
    """Privacy-preserving visitor hash. Same IP + same day = same hash. Raw IP is never stored."""
    raw = f"{ip}:{date_str}:{HASH_SALT}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def log_event(event_type: str, ip: str, path: str = None, meta: dict = None):
    try:
        now = datetime.utcnow()
        date_str = now.strftime("%Y-%m-%d")
        visitor_hash = hash_visitor(ip, date_str)
        meta_json = json.dumps(meta) if meta else None
        with get_db() as conn:
            conn.execute(
                "INSERT INTO events (timestamp, event_type, visitor_hash, path, meta) VALUES (?, ?, ?, ?, ?)",
                (now.isoformat(), event_type, visitor_hash, path, meta_json)
            )
    except Exception as e:
        print(f"Analytics error: {e}", flush=True)


def get_stats() -> dict:
    try:
        with get_db() as conn:
            total_visitors = conn.execute(
                "SELECT COUNT(DISTINCT visitor_hash) FROM events WHERE event_type = 'page_view'"
            ).fetchone()[0]
            total_searches = conn.execute(
                "SELECT COUNT(*) FROM events WHERE event_type = 'search'"
            ).fetchone()[0]
            total_chats = conn.execute(
                "SELECT COUNT(*) FROM events WHERE event_type = 'chat'"
            ).fetchone()[0]
            seven_days_ago = (datetime.utcnow() - timedelta(days=7)).isoformat()
            weekly_visitors = conn.execute(
                "SELECT COUNT(DISTINCT visitor_hash) FROM events WHERE event_type = 'page_view' AND timestamp > ?",
                (seven_days_ago,)
            ).fetchone()[0]
            fourteen_days_ago = (datetime.utcnow() - timedelta(days=14)).isoformat()
            daily = conn.execute("""
                SELECT DATE(timestamp) as day,
                       COUNT(DISTINCT visitor_hash) as visitors,
                       SUM(CASE WHEN event_type = 'search' THEN 1 ELSE 0 END) as searches,
                       SUM(CASE WHEN event_type = 'chat' THEN 1 ELSE 0 END) as chats
                FROM events WHERE timestamp > ?
                GROUP BY DATE(timestamp) ORDER BY day DESC
            """, (fourteen_days_ago,)).fetchall()
            return {
                "total_visitors": total_visitors,
                "total_searches": total_searches,
                "total_chats": total_chats,
                "weekly_visitors": weekly_visitors,
                "daily_breakdown": [dict(row) for row in daily],
            }
    except Exception as e:
        print(f"Stats error: {e}", flush=True)
        return {"total_visitors": 0, "total_searches": 0, "total_chats": 0, "weekly_visitors": 0, "daily_breakdown": []}


init_db()
