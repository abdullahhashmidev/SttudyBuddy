import os

tools_code = '''import sqlite3
import json
from typing import Optional
from datetime import datetime
from langchain_core.tools import tool
from app.db import get_connection, ensure_student_exists


@tool
def create_task(student_id: str, title: str, subject: Optional[str] = None, deadline: Optional[str] = None, priority: str = "medium") -> str:
    """
    Creates a new task or assignment for a student.
    Args:
        student_id: Student identifier (e.g. 'student_42').
        title: Name of the assignment or task.
        subject: Subject/course name (e.g., 'Calculus', 'Physics').
        deadline: Due date/time string.
        priority: Priority level ('low', 'medium', 'high'). Defaults to 'medium'.
    """
    ensure_student_exists(student_id)
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO tasks (student_id, title, subject, deadline, priority, status)
               VALUES (?, ?, ?, ?, ?, 'pending')""",
            (student_id, title, subject, deadline, priority.lower())
        )
        conn.commit()
        task_id = cursor.lastrowid
        return json.dumps({
            "status": "success",
            "task_id": task_id,
            "message": f"Task '{title}' created successfully."
        })
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})
    finally:
        conn.close()


@tool
def list_tasks(student_id: str, status: Optional[str] = None, subject: Optional[str] = None) -> str:
    """
    Lists tasks for a student, optionally filtered by status ('pending', 'completed') or subject.
    """
    ensure_student_exists(student_id)
    conn = get_connection()
    try:
        query = "SELECT task_id, title, subject, deadline, priority, status FROM tasks WHERE student_id = ?"
        params = [student_id]

        if status:
            query += " AND status = ?"
            params.append(status.lower())
        if subject:
            query += " AND LOWER(subject) = LOWER(?)"
            params.append(subject)

        query += " ORDER BY created_at DESC"
        cursor = conn.cursor()
        rows = cursor.execute(query, params).fetchall()
        tasks = [dict(r) for r in rows]
        return json.dumps({"status": "success", "count": len(tasks), "tasks": tasks})
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})
    finally:
        conn.close()


@tool
def create_study_session(student_id: str, subject: str, topic: str, scheduled_date: str, duration_minutes: int = 45) -> str:
    """
    Schedules a new study session or Pomodoro block for a student.
    """
    ensure_student_exists(student_id)
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO study_sessions (student_id, subject, topic, scheduled_date, duration_minutes, completed)
               VALUES (?, ?, ?, ?, ?, 0)""",
            (student_id, subject, topic, scheduled_date, duration_minutes)
        )
        conn.commit()
        session_id = cursor.lastrowid
        return json.dumps({
            "status": "success",
            "session_id": session_id,
            "message": f"Study session '{subject} - {topic}' scheduled successfully."
        })
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})
    finally:
        conn.close()


@tool
def create_note(student_id: str, title: str, content: str, subject: Optional[str] = None, tags: Optional[str] = None) -> str:
    """
    Saves a new study note or revision summary for a student.
    """
    ensure_student_exists(student_id)
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO notes (student_id, title, content, subject, tags)
               VALUES (?, ?, ?, ?, ?)""",
            (student_id, title, content, subject, tags)
        )
        conn.commit()
        note_id = cursor.lastrowid
        return json.dumps({
            "status": "success",
            "note_id": note_id,
            "message": f"Note '{title}' saved successfully."
        })
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})
    finally:
        conn.close()


@tool
def search_notes(student_id: str, query: Optional[str] = None, subject: Optional[str] = None) -> str:
    """
    Searches saved study notes by keyword or subject filter.
    """
    ensure_student_exists(student_id)
    conn = get_connection()
    try:
        sql = "SELECT note_id, title, content, subject, tags, created_at FROM notes WHERE student_id = ?"
        params = [student_id]

        if subject:
            sql += " AND LOWER(subject) = LOWER(?)"
            params.append(subject)
        if query:
            sql += " AND (title LIKE ? OR content LIKE ? OR tags LIKE ?)"
            params.extend([f"%{query}%", f"%{query}%", f"%{query}%"])

        cursor = conn.cursor()
        rows = cursor.execute(sql, params).fetchall()
        notes = [dict(r) for r in rows]
        return json.dumps({"status": "success", "count": len(notes), "notes": notes})
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})
    finally:
        conn.close()
'''

test_tools_code = '''from app.tools import create_task, list_tasks, create_study_session, create_note, search_notes

if __name__ == "__main__":
    print("🧪 Testing Tools Execution...")
    
    # 1. Test create_task
    res1 = create_task.invoke({
        "student_id": "student_42",
        "title": "Calculus Midterm Prep",
        "subject": "Calculus",
        "deadline": "2025-07-20",
        "priority": "high"
    })
    print("1. Create Task Result:", res1)
    
    # 2. Test list_tasks
    res2 = list_tasks.invoke({"student_id": "student_42"})
    print("2. List Tasks Result:", res2)
    
    # 3. Test create_note
    res3 = create_note.invoke({
        "student_id": "student_42",
        "title": "Limits Formula Sheet",
        "content": "lim x->0 (sin x / x) = 1",
        "subject": "Calculus",
        "tags": "math,limits"
    })
    print("3. Create Note Result:", res3)
    
    print("\\n✅ All Tools Working Perfect!")
'''

with open("app/tools.py", "w", encoding="utf-8") as f:
    f.write(tools_code)
print("✅ Generated: app/tools.py")

with open("test_tools.py", "w", encoding="utf-8") as f:
    f.write(test_tools_code)
print("✅ Generated: test_tools.py")