"""
StudyBuddy Tools - local SQLite version (spec: all data stays local).
Each tool returns a JSON string: {"status": "success"|"error", ...}
"""
import json
import sqlite3
from datetime import datetime
from typing import Optional
from app.db import get_connection, ensure_student_exists
from app.pending import save_pending, load_pending, clear_pending
from app.validation import require_text, optional_text, require_positive_int, ValidationError


def _conn():
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    return conn


def _cols(conn, table):
    return {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}


def _pk(conn, table, fallback):
    for r in conn.execute(f"PRAGMA table_info({table})"):
        if r["pk"] == 1:
            return r["name"]
    return fallback


def _insert(conn, table, data):
    cols = _cols(conn, table)
    row = {k: v for k, v in data.items() if k in cols}
    cur = conn.execute(
        f"INSERT INTO {table} ({', '.join(row)}) VALUES ({', '.join('?' for _ in row)})",
        list(row.values()),
    )
    conn.commit()
    return cur.lastrowid


def _ok(**kw):
    return json.dumps({"status": "success", **kw})


def _err(e):
    return json.dumps({"status": "error", "message": str(e)})


def _norm_status(s):
    s = (s or "").lower().strip()
    return {"done": "completed", "complete": "completed", "finished": "completed",
            "todo": "pending", "in progress": "pending"}.get(s, s)


def _norm_priority(p):
    p = (p or "medium").lower().strip()
    return p if p in ("low", "medium", "high") else "medium"


def create_task(student_id: str, title: str, subject: Optional[str] = None,
                deadline: Optional[str] = None, priority: str = "medium") -> str:
    try:
        student_id = require_text(student_id, "student_id", max_len=100)
        title = require_text(title, "title", max_len=200)
        subject = optional_text(subject, "subject", max_len=100)
        deadline = optional_text(deadline, "deadline", max_len=40)
        ensure_student_exists(student_id)
        conn = _conn()
        try:
            task_id = _insert(conn, "tasks", {
                "student_id": student_id, "title": title, "subject": subject,
                "deadline": deadline, "priority": _norm_priority(priority), "status": "pending"})
            return _ok(task_id=task_id, message=f"Task '{title}' created successfully.")
        finally:
            conn.close()
    except Exception as e:
        return _err(e)


def list_tasks(student_id: str, status: Optional[str] = None, subject: Optional[str] = None) -> str:
    try:
        ensure_student_exists(student_id)
        conn = _conn()
        try:
            pk = _pk(conn, "tasks", "task_id")
            sql = "SELECT * FROM tasks WHERE student_id = ?"
            params = [student_id]
            if status:
                sql += " AND status = ?"
                params.append(_norm_status(status))
            if subject:
                sql += " AND LOWER(subject) = LOWER(?)"
                params.append(subject)
            sql += f" ORDER BY {pk} DESC"
            rows = [dict(r) for r in conn.execute(sql, params)]
            for r in rows:
                r.setdefault("task_id", r.get(pk))
            return _ok(count=len(rows), tasks=rows)
        finally:
            conn.close()
    except Exception as e:
        return _err(e)


def update_task(student_id: str, task_id: int, status: Optional[str] = None,
                deadline: Optional[str] = None, priority: Optional[str] = None) -> str:
    try:
        student_id = require_text(student_id, "student_id", max_len=100)
        task_id = require_positive_int(task_id, "task_id")
        deadline = optional_text(deadline, "deadline", max_len=40)
        ensure_student_exists(student_id)
        conn = _conn()
        try:
            pk = _pk(conn, "tasks", "task_id")
            row = conn.execute(f"SELECT 1 FROM tasks WHERE {pk} = ? AND student_id = ?",
                               (task_id, student_id)).fetchone()
            if row is None:
                return _err(f"Task {task_id} not found.")
            fields, params = [], []
            if status:
                fields.append("status = ?")
                params.append(_norm_status(status))
            if deadline:
                fields.append("deadline = ?")
                params.append(deadline)
            if priority:
                fields.append("priority = ?")
                params.append(_norm_priority(priority))
            if not fields:
                return _err("No fields provided to update.")
            params += [task_id, student_id]
            conn.execute(f"UPDATE tasks SET {', '.join(fields)} WHERE {pk} = ? AND student_id = ?", params)
            conn.commit()
            return _ok(task_id=task_id, message="Task updated successfully.")
        finally:
            conn.close()
    except Exception as e:
        return _err(e)


def delete_task(student_id: str, task_id, confirm: bool = False) -> str:
    """Destructive. First call (confirm=False) stages the delete and asks for confirmation.
    Second call (confirm=True) only proceeds if it matches the staged request."""
    try:
        student_id = require_text(student_id, "student_id", max_len=100)
        task_id = require_positive_int(task_id, "task_id")
        ensure_student_exists(student_id)
        conn = _conn()
        try:
            pk = _pk(conn, "tasks", "task_id")
            row = conn.execute(f"SELECT title FROM tasks WHERE {pk} = ? AND student_id = ?",
                               (task_id, student_id)).fetchone()
            if row is None:
                clear_pending(student_id)
                return _err(f"Task {task_id} not found.")
            title = row["title"]

            if not confirm:
                save_pending(student_id, {"action": "delete_task", "task_id": task_id})
                return json.dumps({
                    "status": "confirmation_required",
                    "task_id": task_id,
                    "message": f"'{title}' (Task #{task_id}) delete karne ki confirmation chahiye. "
                               f"Dobara confirm ke saath bolo.",
                })

            pending = load_pending(student_id)
            if not pending or pending.get("action") != "delete_task" or pending.get("task_id") != task_id:
                return _err("Confirmation match nahi hui ya expire ho gayi. Pehle delete request karo.")

            conn.execute(f"DELETE FROM tasks WHERE {pk} = ? AND student_id = ?", (task_id, student_id))
            conn.commit()
            clear_pending(student_id)
            return _ok(task_id=task_id, message=f"Task '{title}' deleted successfully.")
        finally:
            conn.close()
    except ValidationError as e:
        return _err(e)
    except Exception as e:
        return _err(e)


def create_study_session(student_id: str, subject: str, topic: str,
                         scheduled_date: str, duration_minutes: int = 45) -> str:
    try:
        student_id = require_text(student_id, "student_id", max_len=100)
        subject = require_text(subject, "subject", max_len=100)
        topic = require_text(topic, "topic", max_len=100)
        duration_minutes = require_positive_int(duration_minutes, "duration_minutes", max_value=600)
        ensure_student_exists(student_id)
        conn = _conn()
        try:
            session_id = _insert(conn, "study_sessions", {
                "student_id": student_id, "subject": subject, "topic": topic,
                "scheduled_date": scheduled_date, "duration_minutes": int(duration_minutes),
                "completed": 0})
            return _ok(session_id=session_id,
                       message=f"Study session '{subject} - {topic}' scheduled successfully.")
        finally:
            conn.close()
    except Exception as e:
        return _err(e)


def record_study_session(student_id: str, subject: str, topic: str, duration_minutes: int) -> str:
    """Logs a study session that already happened (assignment-required tool)."""
    try:
        student_id = require_text(student_id, "student_id", max_len=100)
        subject = require_text(subject, "subject", max_len=100)
        topic = require_text(topic, "topic", max_len=100)
        duration_minutes = require_positive_int(duration_minutes, "duration_minutes", max_value=600)
        ensure_student_exists(student_id)
        conn = _conn()
        try:
            now = datetime.now().isoformat(timespec="seconds")
            session_id = _insert(conn, "study_sessions", {
                "student_id": student_id, "subject": subject, "topic": topic,
                "duration_minutes": int(duration_minutes), "scheduled_date": now,
                "session_date": now, "completed": 1})
            return _ok(session_id=session_id,
                       message=f"Recorded {int(duration_minutes)} min of {subject} - {topic}.")
        finally:
            conn.close()
    except Exception as e:
        return _err(e)


def create_note(student_id: str, title: str, content: str,
                subject: Optional[str] = None, tags=None) -> str:
    try:
        student_id = require_text(student_id, "student_id", max_len=100)
        title = require_text(title, "title", max_len=200)
        content = require_text(content, "content", max_len=20000)
        subject = optional_text(subject, "subject", max_len=100)
        ensure_student_exists(student_id)
        if isinstance(tags, (list, tuple)):
            tags = ", ".join(map(str, tags))
        conn = _conn()
        try:
            note_id = _insert(conn, "notes", {
                "student_id": student_id, "title": title, "content": content,
                "subject": subject, "tags": tags})
            return _ok(note_id=note_id, message=f"Note '{title}' saved successfully.")
        finally:
            conn.close()
    except Exception as e:
        return _err(e)


def search_notes(student_id: str, query: Optional[str] = None, subject: Optional[str] = None) -> str:
    try:
        ensure_student_exists(student_id)
        conn = _conn()
        try:
            cols = _cols(conn, "notes")
            like_cols = [c for c in ("title", "content", "tags") if c in cols]
            sql = "SELECT * FROM notes WHERE student_id = ?"
            params = [student_id]
            if subject:
                sql += " AND LOWER(subject) = LOWER(?)"
                params.append(subject)
            if query and like_cols:
                sql += " AND (" + " OR ".join(f"{c} LIKE ?" for c in like_cols) + ")"
                params += [f"%{query}%"] * len(like_cols)
            rows = [dict(r) for r in conn.execute(sql, params)]
            return _ok(count=len(rows), notes=rows)
        finally:
            conn.close()
    except Exception as e:
        return _err(e)
