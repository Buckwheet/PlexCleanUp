import sqlite3
import os
from app.config import DB_PATH

def get_db() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS marked_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plex_rating_key TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            year INTEGER,
            file_size INTEGER DEFAULT 0,
            tmdb_id TEXT,
            imdb_id TEXT,
            marked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'pending'
        );
        CREATE TABLE IF NOT EXISTS deletion_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            year INTEGER,
            file_size INTEGER DEFAULT 0,
            deleted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            method TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS scan_state (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            last_scan_at TIMESTAMP,
            next_scan_at TIMESTAMP
        );
        INSERT OR IGNORE INTO scan_state (id) VALUES (1);
    """)
    conn.commit()
    conn.close()


def deletions_today() -> int:
    conn = get_db()
    count = conn.execute(
        "SELECT COUNT(*) as c FROM deletion_log WHERE deleted_at >= datetime('now', '-1 day')"
    ).fetchone()["c"]
    conn.close()
    return count
