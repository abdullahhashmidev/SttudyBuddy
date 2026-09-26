"""
StudyBuddy Database Layer
- Supabase (Postgres): connectivity + schema verification (non-fatal)
- SQLite: working datastore for agent tools & UI queries
"""

import os
import sqlite3
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from app.config import DB_PATH
from app.logger import logger

# ---------------- Supabase (cloud) ----------------
from app.secrets_helper import get_secret
SUPABASE_URL = get_secret("SUPABASE_URL")
SUPABASE_SERVICE_KEY = get_secret("SUPABASE_SERVICE_KEY")

_supabase_client = None


def get_supabase():
    """Return cached Supabase client (lazy import - no crash if pkg missing)."""
    global _supabase_client
    if _supabase_client is None:
        if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
            raise ValueError("SUPABASE_URL / SUPABASE_SERVICE_KEY missing in .env")
        from supabase import create_client
        _supabase_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    return _supabase_client


def verify_supabase() -> bool:
    """Non-fatal connectivity + schema check. App keeps running on SQLite if down."""
    try:
        sb = get_supabase()
        sb.table("students").select("student_id").limit(1).execute()
        logger.info("Supabase reachable - schema OK")
        return True
    except Exception as e:
        logger.warning(f"Supabase not reachable (continuing on SQLite): {e}")
        return False


# ---------------- SQLite (working store) ----------------

def init_db():
    """Initialize local SQLite schema. Never crashes on Supabase issues."""
    Path("data").mkdir(exist_ok=True)
    verify_supabase()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (
            student_id TEXT PRIMARY KEY,
            name TEXT,
            preferred_study_time TEXT,
            daily_available_minutes INTEGER DEFAULT 120
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            task_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            title TEXT NOT NULL,
            subject TEXT,
            deadline TEXT,
            priority TEXT CHECK(priority IN ('low','medium','high')) DEFAULT 'medium',
            status TEXT CHECK(status IN ('pending','completed')) DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(student_id) REFERENCES students(student_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS study_sessions (
            session_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            subject TEXT NOT NULL,
            topic TEXT NOT NULL,
            duration_minutes INTEGER DEFAULT 45,
            scheduled_date TEXT,
            completed INTEGER DEFAULT 0,
            FOREIGN KEY(student_id) REFERENCES students(student_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            note_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            subject TEXT,
            tags TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(student_id) REFERENCES students(student_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS quizzes (
            quiz_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            subject TEXT NOT NULL,
            topic TEXT NOT NULL,
            questions TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(student_id) REFERENCES students(student_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS quiz_attempts (
            attempt_id INTEGER PRIMARY KEY AUTOINCREMENT,
            quiz_id INTEGER NOT NULL,
            student_id TEXT NOT NULL,
            answers TEXT NOT NULL,
            score REAL,
            weak_areas TEXT,
            attempt_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(quiz_id) REFERENCES quizzes(quiz_id),
            FOREIGN KEY(student_id) REFERENCES students(student_id)
        )
    """)

    conn.commit()
    conn.close()
    logger.info(f"Database initialized at: {DB_PATH}")


def get_connection():
    """SQLite connection with Row factory (used by tools + UI queries)."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_student_exists(student_id: str):
    """Create student row if missing (idempotent)."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT student_id FROM students WHERE student_id = ?", (student_id,)
        ).fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO students (student_id, name) VALUES (?, ?)",
                (student_id, f"Student {student_id}")
            )
            conn.commit()
    finally:
        conn.close()
