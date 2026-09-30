import json, os, sqlite3, tempfile, unittest
from unittest import mock

import app.ui_services as svc

SCHEMA = """
CREATE TABLE tasks (task_id INTEGER PRIMARY KEY AUTOINCREMENT, student_id TEXT NOT NULL, title TEXT NOT NULL,
  subject TEXT, deadline TEXT, priority TEXT DEFAULT 'medium', status TEXT DEFAULT 'pending',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE notes (note_id INTEGER PRIMARY KEY AUTOINCREMENT, student_id TEXT NOT NULL, title TEXT NOT NULL,
  content TEXT NOT NULL, subject TEXT, tags TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE quizzes (quiz_id INTEGER PRIMARY KEY AUTOINCREMENT, student_id TEXT NOT NULL, subject TEXT NOT NULL,
  topic TEXT NOT NULL, questions TEXT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE quiz_attempts (attempt_id INTEGER PRIMARY KEY AUTOINCREMENT, quiz_id INTEGER NOT NULL,
  student_id TEXT NOT NULL, answers TEXT NOT NULL, score REAL, weak_areas TEXT,
  attempt_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
"""
SAMPLE = {"questions": [
    {"question": "Q1?", "options": ["A) x", "B) y", "C) z", "D) w"], "correct_answer": "B", "explanation": "e1"},
    {"question": "Q2?", "options": ["x", "y", "z", "w"], "correct_answer": "z", "explanation": "e2"},
]}


class T(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db"); os.close(fd)
        c = sqlite3.connect(self.path); c.executescript(SCHEMA); c.commit(); c.close()
        self.ps = [mock.patch.object(svc, "get_connection", side_effect=self._conn),
                   mock.patch.object(svc, "ensure_student_exists", lambda *_: None)]
        for p in self.ps: p.start()

    def tearDown(self):
        for p in self.ps: p.stop()
        os.remove(self.path)

    def _conn(self):
        c = sqlite3.connect(self.path); c.row_factory = sqlite3.Row; return c

    def _q(self, sql, *a):
        c = self._conn()
        try: return c.execute(sql, a).fetchall()
        finally: c.close()

    # tasks
    def test_add_and_complete_task(self):
        self.assertFalse(svc.add_task("s1", "  ", "x", None, "low")[0])
        self.assertTrue(svc.add_task("s1", "Read", "Math", "2026-10-01", "bogus")[0])
        self.assertEqual(self._q("SELECT priority FROM tasks")[0][0], "medium")
        self.assertTrue(svc.complete_task("s1", "1")[0])
        self.assertEqual(self._q("SELECT status FROM tasks")[0][0], "completed")
        self.assertFalse(svc.complete_task("s1", "abc")[0])
        self.assertFalse(svc.complete_task("other", 1)[0])
        self.assertFalse(svc.complete_task("s1", 999)[0])

    def test_task_search_and_escape(self):
        svc.add_task("s1", "100% done", "Bio", None, "low")
        svc.add_task("s1", "Essay", "History", None, "low")
        svc.add_task("s2", "Essay other user", "History", None, "low")
        self.assertEqual(len(svc.get_tasks_df("s1")), 2)
        self.assertEqual(len(svc.get_tasks_df("s1", "essay")), 1)
        self.assertEqual(len(svc.get_tasks_df("s1", "history")), 1)
        self.assertEqual(len(svc.get_tasks_df("s1", "%")), 1)
        self.assertEqual(len(svc.get_tasks_df("s1", "nomatch")), 0)
        self.assertEqual(len(svc.get_tasks_df("s1", "")), 2)

    # notes
    def test_notes_add_and_search(self):
        self.assertFalse(svc.add_note("s1", "", "x", "y")[0])
        svc.add_note("s1", "Agents", "AI", "LangGraph loop")
        svc.add_note("s1", "Cells", "Bio", "mitochondria")
        self.assertEqual(len(svc.get_notes_df("s1", "langgraph")), 1)
        self.assertEqual(len(svc.get_notes_df("s1", "bio")), 1)
        self.assertEqual(len(svc.get_notes_df("s1")), 2)

    # quiz
    def test_normalize(self):
        qs = svc._normalize_questions(SAMPLE, 5)
        self.assertEqual([q["correct_answer"] for q in qs], ["B", "C"])
        self.assertTrue(all(o[1] == ")" for q in qs for o in q["options"]))
        with self.assertRaises(ValueError): svc._normalize_questions({"questions": []}, 3)

    def test_create_and_grade_quiz(self):
        raw = "```json\n" + json.dumps(SAMPLE) + "\n```"
        with mock.patch.object(svc, "_call_llm", return_value=raw):
            ok, _, data = svc.create_quiz("s1", "AI", "Agents", 5)
        self.assertTrue(ok)
        ok, _, res = svc.grade_quiz("s1", data["quiz_id"], {"q1": "B", "q2": "C"})
        self.assertTrue(ok); self.assertEqual(res["score"], 100.0)
        ok, _, res = svc.grade_quiz("s1", data["quiz_id"], {"q1": "A"})
        self.assertEqual(res["score"], 0.0)
        self.assertEqual(len(self._q("SELECT * FROM quiz_attempts")), 2)
        self.assertFalse(svc.grade_quiz("s1", 999, {})[0])
        self.assertEqual(len(svc.get_quiz_history_df("s1")), 2)
        self.assertEqual(svc.db_stats("s1")["quizzes"], 2)

    def test_create_quiz_failures(self):
        with mock.patch.object(svc, "_call_llm", side_effect=RuntimeError("boom")):
            ok, msg, _ = svc.create_quiz("s1", "AI", "Agents", 5, retries=0)
        self.assertFalse(ok); self.assertIn("boom", msg)
        self.assertFalse(svc.create_quiz("s1", " ", "x")[0])

    def test_stats(self):
        svc.add_task("s1", "a", "", None, "low"); svc.add_task("s1", "b", "", None, "low")
        svc.complete_task("s1", 1); svc.add_note("s1", "n", "", "c")
        st = svc.db_stats("s1")
        self.assertEqual((st["tasks"], st["pending_tasks"], st["notes"]), (2, 1, 1))


if __name__ == "__main__":
    unittest.main()
