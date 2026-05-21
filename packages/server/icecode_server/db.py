"""
ICECODE Server — SQLite database initialization.

Uses raw sqlite3 (WAL mode + FTS5) for sessions and agent data.
SQLAlchemy is available for routes that need ORM-style access.
"""
from __future__ import annotations

import sqlite3
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from loguru import logger

SCHEMA_VERSION = 1


def get_db_path() -> Path:
    from icecode.config.settings import ICECodeSettings
    return ICECodeSettings().db_path


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    # WAL mode for concurrent reads
    try:
        conn.execute("PRAGMA journal_mode=WAL")
    except sqlite3.OperationalError:
        conn.execute("PRAGMA journal_mode=DELETE")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def init_db(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """Initialize all tables and return connection."""
    if db_path is None:
        db_path = get_db_path()

    conn = _connect(db_path)

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL
        );

        -- Chat sessions
        CREATE TABLE IF NOT EXISTS sessions (
            id          TEXT PRIMARY KEY,
            title       TEXT NOT NULL DEFAULT 'Untitled',
            model       TEXT,
            provider    TEXT,
            created_at  TEXT NOT NULL,
            updated_at  TEXT NOT NULL,
            message_count INTEGER DEFAULT 0,
            total_tokens  INTEGER DEFAULT 0,
            source      TEXT DEFAULT 'web'
        );

        -- Individual messages
        CREATE TABLE IF NOT EXISTS messages (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id  TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
            role        TEXT NOT NULL CHECK(role IN ('user','assistant','system','tool')),
            content     TEXT NOT NULL,
            model       TEXT,
            tokens      INTEGER DEFAULT 0,
            created_at  TEXT NOT NULL
        );

        -- Usage stats per model
        CREATE TABLE IF NOT EXISTS usage_stats (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id  TEXT,
            model       TEXT NOT NULL,
            provider    TEXT,
            prompt_tokens     INTEGER DEFAULT 0,
            completion_tokens INTEGER DEFAULT 0,
            cost_usd    REAL DEFAULT 0.0,
            recorded_at TEXT NOT NULL
        );

        -- Kanban tasks
        CREATE TABLE IF NOT EXISTS kanban_tasks (
            id          TEXT PRIMARY KEY,
            title       TEXT NOT NULL,
            description TEXT,
            status      TEXT NOT NULL DEFAULT 'todo',
            priority    TEXT DEFAULT 'medium',
            session_id  TEXT,
            created_at  TEXT NOT NULL,
            updated_at  TEXT NOT NULL
        );

        -- FTS index for session search
        CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
            content,
            session_id UNINDEXED,
            content=messages,
            content_rowid=id
        );
    """)

    # Record schema version
    conn.execute(
        "INSERT OR IGNORE INTO schema_version (version, applied_at) VALUES (?, ?)",
        (SCHEMA_VERSION, datetime.now(timezone.utc).isoformat())
    )
    conn.commit()

    logger.debug(f"DB initialized at {db_path}")
    return conn


# ── Simple DAO helpers used by routes ──────────────────────────────────────

_conn: Optional[sqlite3.Connection] = None


def get_connection() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = init_db()
    return _conn


def record_usage(session_id: str, model: str, provider: str,
                 prompt_tokens: int, completion_tokens: int, cost_usd: float = 0.0):
    conn = get_connection()
    conn.execute(
        """INSERT INTO usage_stats
           (session_id, model, provider, prompt_tokens, completion_tokens, cost_usd, recorded_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (session_id, model, provider, prompt_tokens, completion_tokens,
         cost_usd, datetime.now(timezone.utc).isoformat())
    )
    conn.commit()


def get_usage_summary() -> Dict[str, Any]:
    conn = get_connection()
    rows = conn.execute("""
        SELECT model, provider,
               SUM(prompt_tokens) as prompt,
               SUM(completion_tokens) as completion,
               SUM(cost_usd) as cost,
               COUNT(DISTINCT session_id) as sessions
        FROM usage_stats GROUP BY model, provider
    """).fetchall()

    total_prompt = sum(r["prompt"] for r in rows)
    total_completion = sum(r["completion"] for r in rows)

    return {
        "total_tokens": total_prompt + total_completion,
        "total_prompt": total_prompt,
        "total_completion": total_completion,
        "total_cost_usd": round(sum(r["cost"] for r in rows), 6),
        "total_sessions": conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0],
        "total_tool_calls": 0,
        "by_model": {
            r["model"]: {
                "prompt": r["prompt"],
                "completion": r["completion"],
                "total": r["prompt"] + r["completion"],
                "cost": round(r["cost"], 6),
                "sessions": r["sessions"],
            }
            for r in rows
        }
    }
