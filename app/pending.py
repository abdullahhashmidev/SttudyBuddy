"""
Pending destructive actions (human-in-the-loop confirmation).
Stored in SQLite so a pending delete survives between turns, Streamlit reruns and restarts,
independent of whatever state the caller passes in.
"""
import json
from datetime import datetime
from app.db import get_connection


def _ensure(conn):
    conn.execute(
        """CREATE TABLE IF NOT EXISTS pending_actions (
               student_id TEXT PRIMARY KEY,
               payload TEXT NOT NULL,
               created_at TEXT NOT NULL)"""
    )


def save_pending(student_id: str, payload: dict) -> None:
    conn = get_connection()
    try:
        _ensure(conn)
        conn.execute(
            "INSERT OR REPLACE INTO pending_actions (student_id, payload, created_at) VALUES (?, ?, ?)",
            (student_id, json.dumps(payload), datetime.now().isoformat(timespec="seconds")),
        )
        conn.commit()
    finally:
        conn.close()


def load_pending(student_id: str):
    conn = get_connection()
    try:
        _ensure(conn)
        row = conn.execute(
            "SELECT payload FROM pending_actions WHERE student_id = ?", (student_id,)
        ).fetchone()
        return json.loads(row[0]) if row else None
    except Exception:
        return None
    finally:
        conn.close()


def clear_pending(student_id: str) -> None:
    conn = get_connection()
    try:
        _ensure(conn)
        conn.execute("DELETE FROM pending_actions WHERE student_id = ?", (student_id,))
        conn.commit()
    finally:
        conn.close()
