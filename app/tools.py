"""
StudyBuddy Tools — Supabase Postgres version
"""

import json
from typing import Optional
from app.db import get_supabase, ensure_student_exists


def create_task(student_id: str, title: str, subject: Optional[str] = None,
                deadline: Optional[str] = None, priority: str = "medium") -> str:
    ensure_student_exists(student_id)
    try:
        sb = get_supabase()
        res = sb.table("tasks").insert({
            "student_id": student_id,
            "title": title,
            "subject": subject,
            "deadline": deadline,
            "priority": priority.lower(),
            "status": "pending",
        }).execute()
        task_id = res.data[0]["task_id"]
        return json.dumps({"status": "success", "task_id": task_id,
                            "message": f"Task '{title}' created successfully."})
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})


def list_tasks(student_id: str, status: Optional[str] = None, subject: Optional[str] = None) -> str:
    ensure_student_exists(student_id)
    try:
        sb = get_supabase()
        query = (sb.table("tasks")
                 .select("task_id,title,subject,deadline,priority,status")
                 .eq("student_id", student_id))
        if status:
            query = query.eq("status", status.lower())
        if subject:
            query = query.ilike("subject", subject)
        res = query.order("created_at", desc=True).execute()
        task_list = res.data or []
        return json.dumps({"status": "success", "count": len(task_list), "tasks": task_list})
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})


def update_task(student_id: str, task_id: int, status: Optional[str] = None,
                deadline: Optional[str] = None, priority: Optional[str] = None) -> str:
    ensure_student_exists(student_id)
    try:
        sb = get_supabase()
        existing = (sb.table("tasks").select("task_id")
                    .eq("task_id", task_id).eq("student_id", student_id).execute())
        if not existing.data:
            return json.dumps({"status": "error", "message": f"Task {task_id} not found."})
        updates = {}
        if status:
            updates["status"] = status.lower()
        if deadline:
            updates["deadline"] = deadline
        if priority:
            updates["priority"] = priority.lower()
        if not updates:
            return json.dumps({"status": "error", "message": "No fields provided to update."})
        sb.table("tasks").update(updates).eq("task_id", task_id).eq("student_id", student_id).execute()
        return json.dumps({"status": "success", "task_id": task_id, "message": "Task updated successfully."})
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})


def delete_task(student_id: str, task_id: int) -> str:
    ensure_student_exists(student_id)
    try:
        sb = get_supabase()
        existing = (sb.table("tasks").select("task_id")
                    .eq("task_id", task_id).eq("student_id", student_id).execute())
        if not existing.data:
            return json.dumps({"status": "error", "message": f"Task {task_id} not found."})
        sb.table("tasks").delete().eq("task_id", task_id).eq("student_id", student_id).execute()
        return json.dumps({"status": "success", "task_id": task_id, "message": "Task deleted successfully."})
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})


def create_study_session(student_id: str, subject: str, topic: str,
                         scheduled_date: str, duration_minutes: int = 45) -> str:
    ensure_student_exists(student_id)
    try:
        sb = get_supabase()
        res = sb.table("study_sessions").insert({
            "student_id": student_id, "subject": subject, "topic": topic,
            "scheduled_date": scheduled_date, "duration_minutes": duration_minutes, "completed": 0,
        }).execute()
        session_id = res.data[0]["session_id"]
        return json.dumps({"status": "success", "session_id": session_id,
                            "message": f"Study session '{subject} - {topic}' scheduled successfully."})
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})


def create_note(student_id: str, title: str, content: str,
                subject: Optional[str] = None, tags: Optional[str] = None) -> str:
    ensure_student_exists(student_id)
    try:
        sb = get_supabase()
        res = sb.table("notes").insert({
            "student_id": student_id, "title": title, "content": content,
            "subject": subject, "tags": tags,
        }).execute()
        note_id = res.data[0]["note_id"]
        return json.dumps({"status": "success", "note_id": note_id,
                            "message": f"Note '{title}' saved successfully."})
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})


def search_notes(student_id: str, query: Optional[str] = None, subject: Optional[str] = None) -> str:
    ensure_student_exists(student_id)
    try:
        sb = get_supabase()
        q = (sb.table("notes")
             .select("note_id,title,content,subject,tags,created_at")
             .eq("student_id", student_id))
        if subject:
            q = q.ilike("subject", subject)
        if query:
            q = q.or_(f"title.ilike.%{query}%,content.ilike.%{query}%,tags.ilike.%{query}%")
        res = q.execute()
        note_list = res.data or []
        return json.dumps({"status": "success", "count": len(note_list), "notes": note_list})
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})
