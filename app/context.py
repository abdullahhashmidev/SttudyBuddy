"""
Builds the 'saved data' context (profile, tasks with days left, recent study time) that the
Tutor gives the LLM, so answers come from the real database instead of guesses.
"""
import json
import sqlite3
from collections import defaultdict
from datetime import datetime

from dateutil import parser as dtparser

from app import tools
from app.db import get_connection


def _to_date(value):
    if not value:
        return None
    try:
        return dtparser.parse(str(value)).date()
    except (ValueError, OverflowError):
        return None


def build_student_context(user_id: str, now: datetime | None = None) -> str:
    now = now or datetime.now()
    today = now.date()
    lines = [f"TODAY: {today:%A, %Y-%m-%d}"]
    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        try:
            prof = conn.execute("SELECT * FROM students WHERE student_id = ?", (user_id,)).fetchone()
            sessions = [dict(r) for r in conn.execute(
                "SELECT * FROM study_sessions WHERE student_id = ? ORDER BY rowid DESC LIMIT 300",
                (user_id,))]
        finally:
            conn.close()

        if prof:
            p = dict(prof)
            bits = []
            if p.get("name") and not str(p["name"]).startswith("Student "):
                bits.append(f"name={p['name']}")
            if p.get("preferred_study_time"):
                bits.append(f"preferred study time={p['preferred_study_time']}")
            if p.get("daily_available_minutes"):
                bits.append(f"daily available minutes={p['daily_available_minutes']}")
            if bits:
                lines.append("PROFILE: " + ", ".join(bits))

        tasks = json.loads(tools.list_tasks(student_id=user_id)).get("tasks", [])
        if tasks:
            rows = []
            for t in tasks:
                d = _to_date(t.get("deadline"))
                left = (d - today).days if d else None
                rows.append((t, left))
            rows.sort(key=lambda x: (x[0].get("status") != "pending", x[1] is None, x[1] if x[1] is not None else 0))
            lines.append("TASKS (pending first, nearest deadline first):")
            for t, left in rows[:30]:
                if left is None:
                    extra = ""
                elif left >= 0:
                    extra = f" | {left} day(s) left"
                else:
                    extra = f" | OVERDUE by {-left} day(s)"
                lines.append(
                    f"- [{t.get('task_id')}] {t.get('title')} | subject={t.get('subject')} | "
                    f"priority={t.get('priority')} | status={t.get('status')} | "
                    f"deadline={t.get('deadline')}{extra}")
        else:
            lines.append("TASKS: none saved yet.")

        week = defaultdict(int)
        count = 0
        upcoming = []
        for s in sessions:
            if s.get("completed"):
                when = _to_date(s.get("session_date") or s.get("scheduled_date"))
                if when and 0 <= (today - when).days <= 6:
                    week[s.get("subject") or "Other"] += int(s.get("duration_minutes") or 0)
                    count += 1
            else:
                sched = _to_date(s.get("scheduled_date"))
                if sched and sched >= today:
                    upcoming.append((sched, s))

        if count:
            total = sum(week.values())
            per = ", ".join(f"{k}: {v} min" for k, v in week.items())
            lines.append(f"STUDY TIME, last 7 days: {total} min in {count} completed session(s) ({per}).")
        else:
            lines.append("STUDY TIME, last 7 days: no completed study sessions recorded.")

        if upcoming:
            upcoming.sort(key=lambda x: x[0])
            lines.append("UPCOMING PLANNED SESSIONS:")
            for _, s in upcoming[:8]:
                lines.append(f"- {s.get('scheduled_date')}: {s.get('subject')} - {s.get('topic')} "
                             f"({s.get('duration_minutes')} min)")
    except Exception as e:
        lines.append(f"(could not load some saved data: {e})")
    return "\n".join(lines)
