"""Privacy-conscious local usage counters for the Streamlit prototype.
Counts app sessions and province selections. Local SQLite storage may reset on ephemeral hosting.
"""
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

DB_PATH = Path(__file__).resolve().parent / "data" / "usage_analytics.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

def _connect():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            started_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS province_views (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            province TEXT NOT NULL,
            viewed_at TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn

def register_session(session_id: str):
    with _connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO sessions(session_id, started_at) VALUES (?, ?)",
            (session_id, datetime.now(timezone.utc).isoformat())
        )

def record_province(session_id: str, province: str):
    with _connect() as conn:
        conn.execute(
            "INSERT INTO province_views(session_id, province, viewed_at) VALUES (?, ?, ?)",
            (session_id, province, datetime.now(timezone.utc).isoformat())
        )

def get_usage_stats():
    with _connect() as conn:
        total_sessions = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        total_views = conn.execute("SELECT COUNT(*) FROM province_views").fetchone()[0]
        top = conn.execute("""
            SELECT province, COUNT(*) AS n
            FROM province_views GROUP BY province
            ORDER BY n DESC LIMIT 5
        """).fetchall()
    return {"sessions": total_sessions, "province_views": total_views, "top_provinces": top}
