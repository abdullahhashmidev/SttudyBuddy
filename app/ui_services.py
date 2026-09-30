"""StudyBuddy UI service layer: every DB/LLM action used by app_ui.py.

Rules: no Streamlit imports here (testable), public action functions never raise,
every connection is closed in `finally`, every query is scoped by student_id.
"""
from __future__ import annotations

import json
import logging
import re

import pandas as pd

from app.db import get_connection, ensure_student_exists

log = logging.getLogger("studybuddy.ui")
LETTERS = "ABCD"
MAX_FIELD_LEN = 80
PRIORITIES = ("low", "medium", "high")


# ------------------------------------------------------------ generic helpers
def _like(q: str) -> str:
    esc = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{esc}%"


def _read_df(sql: str, params) -> pd.DataFrame:
    conn = None
    try:
        conn = get_connection()
        return pd.read_sql_query(sql, conn, params=params)
    except Exception:  # noqa: BLE001
        log.exception("read failed: %s", sql[:80])
        return pd.DataFrame()
    finally:
        if conn is not None:
            conn.close()


def _execute(sql: str, params):
    """Run one write. Returns (ok, rowcount_or_error, lastrowid)."""
    conn = None
    try:
        conn = get_connection()
        cur = conn.execute(sql, params)
        conn.commit()
        return True, cur.rowcount, cur.lastrowid
    except Exception as e:  # noqa: BLE001
        log.exception("write failed: %s", sql[:80])
        return False, str(e), None
    finally:
        if conn is not None:
            conn.close()


# ------------------------------------------------------------ stats / reads
def db_stats(student_id: str) -> dict:
    empty = {"tasks": 0, "pending_tasks": 0, "notes": 0, "quizzes": 0}
    conn = None
    try:
        conn = get_connection()
        q = lambda sql: conn.execute(sql, (student_id,)).fetchone()[0]  # noqa: E731
        return {
            "tasks": q("SELECT COUNT(*) FROM tasks WHERE student_id = ?"),
            "pending_tasks": q("SELECT COUNT(*) FROM tasks WHERE student_id = ? AND status = 'pending'"),
            "notes": q("SELECT COUNT(*) FROM notes WHERE student_id = ?"),
            "quizzes": q("SELECT COUNT(*) FROM quiz_attempts WHERE student_id = ?"),
        }
    except Exception:  # noqa: BLE001
        log.exception("db_stats failed")
        return empty
    finally:
        if conn is not None:
            conn.close()


def get_tasks_df(student_id: str, query: str = "") -> pd.DataFrame:
    sql = ("SELECT task_id, title, subject, deadline, priority, status, created_at "
           "FROM tasks WHERE student_id = ?")
    params = [student_id]
    q = (query or "").strip()
    if q:
        sql += " AND (title LIKE ? ESCAPE '\\' OR IFNULL(subject,'') LIKE ? ESCAPE '\\')"
        params += [_like(q), _like(q)]
    sql += " ORDER BY created_at DESC, task_id DESC"
    return _read_df(sql, params)


def get_notes_df(student_id: str, query: str = "") -> pd.DataFrame:
    sql = ("SELECT note_id, title, subject, content, tags, created_at "
           "FROM notes WHERE student_id = ?")
    params = [student_id]
    q = (query or "").strip()
    if q:
        sql += (" AND (title LIKE ? ESCAPE '\\' OR content LIKE ? ESCAPE '\\'"
                " OR IFNULL(subject,'') LIKE ? ESCAPE '\\')")
        params += [_like(q)] * 3
    sql += " ORDER BY created_at DESC, note_id DESC"
    return _read_df(sql, params)


def get_quiz_history_df(student_id: str) -> pd.DataFrame:
    return _read_df(
        "SELECT qa.attempt_id, q.subject, q.topic, qa.score, qa.attempt_date "
        "FROM quiz_attempts qa JOIN quizzes q ON qa.quiz_id = q.quiz_id "
        "WHERE qa.student_id = ? ORDER BY qa.attempt_date DESC, qa.attempt_id DESC",
        [student_id],
    )


# ------------------------------------------------------------ tasks / notes
def add_task(student_id, title, subject, deadline, priority):
    title = (title or "").strip()[:200]
    if not title:
        return False, "Task title zaroori hai."
    priority = priority if priority in PRIORITIES else "medium"
    try:
        ensure_student_exists(student_id)
    except Exception:  # noqa: BLE001
        log.exception("ensure_student_exists failed")
    ok, res, _ = _execute(
        "INSERT INTO tasks (student_id, title, subject, deadline, priority, status) "
        "VALUES (?, ?, ?, ?, ?, 'pending')",
        (student_id, title, (subject or "").strip(), str(deadline) if deadline else None, priority),
    )
    return (True, "Task added!") if ok else (False, f"DB error: {res}")


def complete_task(student_id, task_id):
    try:
        tid = int(task_id)
    except (TypeError, ValueError):
        return False, "Invalid task ID."
    ok, res, _ = _execute(
        "UPDATE tasks SET status = 'completed' WHERE task_id = ? AND student_id = ?",
        (tid, student_id),
    )
    if not ok:
        return False, f"DB error: {res}"
    if res == 0:
        return False, f"Task #{tid} nahi mila."
    return True, f"Task #{tid} marked completed!"


def add_note(student_id, title, subject, content):
    title = (title or "").strip()[:200]
    if not title:
        return False, "Note title zaroori hai."
    try:
        ensure_student_exists(student_id)
    except Exception:  # noqa: BLE001
        log.exception("ensure_student_exists failed")
    ok, res, _ = _execute(
        "INSERT INTO notes (student_id, title, subject, content) VALUES (?, ?, ?, ?)",
        (student_id, title, (subject or "").strip(), (content or "").strip()),
    )
    return (True, "Note saved!") if ok else (False, f"DB error: {res}")


# ------------------------------------------------------------ quiz
def _call_llm(prompt: str) -> str:
    from langchain_groq import ChatGroq
    from langchain_core.messages import HumanMessage
    from app.config import GROQ_API_KEY, DEFAULT_MODEL

    llm = ChatGroq(model=DEFAULT_MODEL, api_key=GROQ_API_KEY, temperature=0.7)
    return llm.invoke([HumanMessage(content=prompt)]).content


def _extract_json(raw: str):
    raw = (raw or "").replace("```json", "").replace("```", "").strip()
    a, b = raw.find("{"), raw.rfind("}")
    if a == -1 or b <= a:
        raise ValueError("AI response mein JSON nahi mila")
    return json.loads(raw[a : b + 1])


def _normalize_questions(data, limit: int):
    qs = data.get("questions") if isinstance(data, dict) else None
    if not isinstance(qs, list) or not qs:
        raise ValueError("AI response mein questions nahi the")
    out = []
    for q in qs:
        if not isinstance(q, dict):
            continue
        text = str(q.get("question", "")).strip()
        opts = q.get("options")
        if not text or not isinstance(opts, list) or len(opts) != 4:
            continue
        clean = [re.sub(r"^\s*[A-Da-d][\)\.\:\-]\s*", "", str(o)).strip() for o in opts]
        if any(not c for c in clean):
            continue
        raw_ans = str(q.get("correct_answer", "")).strip()
        idx = next((i for i, c in enumerate(clean) if c.lower() == raw_ans.lower()), None)
        if idx is None:
            m = re.match(r"^([A-Da-d])(?:[\)\.\:]|$)", raw_ans)
            if not m:
                continue
            idx = LETTERS.index(m.group(1).upper())
        out.append({
            "question": text,
            "options": [f"{LETTERS[i]}) {c}" for i, c in enumerate(clean)],
            "correct_answer": LETTERS[idx],
            "explanation": str(q.get("explanation", "")).strip(),
        })
    if not out:
        raise ValueError("Koi valid question nahi bana")
    return out[:limit]


def create_quiz(student_id, subject, topic, num_questions=5, retries=2):
    subject = (subject or "").strip()[:MAX_FIELD_LEN]
    topic = (topic or "").strip()[:MAX_FIELD_LEN]
    if not subject or not topic:
        return False, "Subject aur Topic dono zaroori hain.", None
    try:
        n = max(1, min(10, int(num_questions)))
    except (TypeError, ValueError):
        n = 5
    prompt = (
        f"Generate a {n}-question multiple choice quiz on {subject} - {topic}. "
        "Each question must have exactly 4 options and exactly one correct answer. "
        'Return ONLY valid JSON: {"questions": [{"question": "...", '
        '"options": ["A) ...", "B) ...", "C) ...", "D) ..."], '
        '"correct_answer": "B", "explanation": "..."}]}'
    )
    last_err, questions = "unknown error", None
    for attempt in range(max(0, retries) + 1):
        try:
            questions = _normalize_questions(_extract_json(_call_llm(prompt)), n)
            break
        except Exception as e:  # noqa: BLE001
            last_err = str(e)
            log.warning("quiz generation attempt %s failed: %s", attempt + 1, e)
    if questions is None:
        return False, f"AI quiz generate nahi kar saka ({last_err}). Dobara try karo.", None
    try:
        ensure_student_exists(student_id)
    except Exception:  # noqa: BLE001
        log.exception("ensure_student_exists failed")
    ok, res, qid = _execute(
        "INSERT INTO quizzes (student_id, subject, topic, questions) VALUES (?, ?, ?, ?)",
        (student_id, subject, topic, json.dumps({"questions": questions})),
    )
    if not ok:
        return False, f"DB error: {res}", None
    return True, f"Quiz ready: {subject} - {topic}", {"quiz_id": qid, "questions": questions}


def grade_quiz(student_id, quiz_id, answers: dict):
    """Grade against the STORED quiz (source of truth) and save the attempt."""
    conn = None
    try:
        conn = get_connection()
        row = conn.execute(
            "SELECT questions FROM quizzes WHERE quiz_id = ? AND student_id = ?",
            (quiz_id, student_id),
        ).fetchone()
        if not row:
            return False, "Quiz DB mein nahi mila.", None
        questions = json.loads(row[0])["questions"]
        results, correct, weak = [], 0, []
        for i, q in enumerate(questions, 1):
            given = str(answers.get(f"q{i}", "")).strip().upper()
            right = str(q["correct_answer"]).strip().upper()
            ok = given == right
            correct += int(ok)
            if not ok:
                weak.append(q["question"])
            results.append({
                "question": q["question"], "your_answer": given or "-",
                "correct_answer": right, "is_correct": ok,
                "explanation": q.get("explanation", ""),
            })
        total = len(questions)
        score = round(correct / total * 100, 1) if total else 0.0
        conn.execute(
            "INSERT INTO quiz_attempts (quiz_id, student_id, answers, score, weak_areas) VALUES (?, ?, ?, ?, ?)",
            (quiz_id, student_id, json.dumps(answers), score, json.dumps(weak)),
        )
        conn.commit()
        return True, "Quiz graded.", {"score": score, "correct": correct, "total": total, "results": results}
    except Exception as e:  # noqa: BLE001
        log.exception("grade_quiz failed")
        return False, f"Grading error: {e}", None
    finally:
        if conn is not None:
            conn.close()
