import os

files = {
    "requirements.txt": """langgraph
langchain
langchain-openai
python-dotenv
pydantic
python-dateutil
groq
langchain-groq""",

    ".env": """GROQ_API_KEY=your_groq_api_key_here
DB_PATH=data/studybuddy.db""",

    "app/config.py": """import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
DB_PATH = os.getenv("DB_PATH", "data/studybuddy.db")
DEFAULT_MODEL = "llama-3.3-70b-versatile\"""",

    "app/schema.sql": """CREATE TABLE IF NOT EXISTS students (
    student_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    preferred_study_time TEXT,
    daily_available_minutes INTEGER DEFAULT 120
);

CREATE TABLE IF NOT EXISTS tasks (
    task_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT NOT NULL,
    title TEXT NOT NULL,
    subject TEXT,
    deadline TEXT,
    priority TEXT CHECK(priority IN ('low','medium','high')) DEFAULT 'medium',
    status TEXT CHECK(status IN ('pending','completed','overdue')) DEFAULT 'pending',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(student_id) REFERENCES students(student_id)
);

CREATE TABLE IF NOT EXISTS study_sessions (
    session_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT NOT NULL,
    subject TEXT,
    topic TEXT,
    scheduled_date TEXT,
    duration_minutes INTEGER,
    completed INTEGER DEFAULT 0,
    session_date TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(student_id) REFERENCES students(student_id)
);

CREATE TABLE IF NOT EXISTS notes (
    note_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT NOT NULL,
    title TEXT,
    content TEXT, 
    subject TEXT,
    tags TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(student_id) REFERENCES students(student_id)
);

CREATE TABLE IF NOT EXISTS quiz_results (
    quiz_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT NOT NULL,
    subject TEXT,
    topic TEXT,
    score REAL,
    weak_areas TEXT,
    taken_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(student_id) REFERENCES students(student_id)
);""",

    "app/db.py": """import sqlite3
import os
from pathlib import Path
from app.config import DB_PATH


def get_connection() -> sqlite3.Connection:
    Path(os.path.dirname(DB_PATH)).mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def init_db():
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    with open(schema_path, "r") as f:
        schema_sql = f.read()

    conn = get_connection()
    try:
        conn.executescript(schema_sql)
        conn.commit()
    finally:
        conn.close()


def ensure_student_exists(student_id: str, name: str = "Student",
                           preferred_study_time: str = "evening",
                           daily_available_minutes: int = 120) -> dict:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM students WHERE student_id = ?", (student_id,)
        ).fetchone()

        if row is None:
            conn.execute(
                \"\"\"INSERT INTO students
                   (student_id, name, preferred_study_time, daily_available_minutes)
                   VALUES (?, ?, ?, ?)\"\"\",
                (student_id, name, preferred_study_time, daily_available_minutes)
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM students WHERE student_id = ?", (student_id,)
            ).fetchone()

        return dict(row)
    finally:
        conn.close()""",

    "seed.py": """from app.db import init_db, ensure_student_exists

if __name__ == "__main__":
    init_db()
    student = ensure_student_exists(
        student_id="student_42",
        name="Abdullah",
        preferred_study_time="evening",
        daily_available_minutes=120
    )
    print("DB initialized. Demo student ready:")
    print(student)"""
}

for path, content in files.items():
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:     
        f.write(content)
    print(f"✅ Generated: {path}")

print("\n🚀 All files created successfully!")