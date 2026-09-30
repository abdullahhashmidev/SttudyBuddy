"""Master safety/validation tests: delete confirmation gate + input validation."""
import json, os, sqlite3, tempfile, unittest
from unittest import mock

import app.tools as tools
import app.pending as pending

SCHEMA = """
CREATE TABLE tasks (task_id INTEGER PRIMARY KEY AUTOINCREMENT, student_id TEXT NOT NULL, title TEXT NOT NULL,
  subject TEXT, deadline TEXT, priority TEXT DEFAULT 'medium', status TEXT DEFAULT 'pending',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE notes (note_id INTEGER PRIMARY KEY AUTOINCREMENT, student_id TEXT NOT NULL, title TEXT NOT NULL,
  content TEXT NOT NULL, subject TEXT, tags TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE study_sessions (session_id INTEGER PRIMARY KEY AUTOINCREMENT, student_id TEXT NOT NULL,
  subject TEXT NOT NULL, topic TEXT NOT NULL, duration_minutes INTEGER DEFAULT 45,
  scheduled_date TEXT, session_date TEXT, completed INTEGER DEFAULT 0);
"""


class ToolsSafetyTest(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db"); os.close(fd)
        c = sqlite3.connect(self.path); c.executescript(SCHEMA); c.commit(); c.close()
        self.patches = [
            mock.patch.object(tools, "get_connection", side_effect=self._conn),
            mock.patch.object(tools, "ensure_student_exists", lambda *_: None),
            mock.patch.object(pending, "get_connection", side_effect=self._conn),
        ]
        for p in self.patches: p.start()

    def tearDown(self):
        for p in self.patches: p.stop()
        os.remove(self.path)

    def _conn(self):
        c = sqlite3.connect(self.path); c.row_factory = sqlite3.Row; return c

    # ---- input validation
    def test_create_task_rejects_empty_and_oversized_title(self):
        self.assertEqual(json.loads(tools.create_task("s1", "   "))["status"], "error")
        self.assertEqual(json.loads(tools.create_task("s1", "x" * 500))["status"], "error")

    def test_create_task_ok(self):
        self.assertEqual(json.loads(tools.create_task("s1", "Read ch3", subject="Bio"))["status"], "success")

    def test_create_note_rejects_empty_content(self):
        self.assertEqual(json.loads(tools.create_note("s1", "Title", "   "))["status"], "error")

    def test_study_session_rejects_bad_duration(self):
        self.assertEqual(
            json.loads(tools.create_study_session("s1", "AI", "Agents", "2026-10-01", -5))["status"], "error"
        )
        self.assertEqual(
            json.loads(tools.create_study_session("s1", "AI", "Agents", "2026-10-01", 9999))["status"], "error"
        )

    def test_update_task_no_fields_errors(self):
        tid = json.loads(tools.create_task("s1", "Task"))["task_id"]
        self.assertEqual(json.loads(tools.update_task("s1", tid))["status"], "error")

    # ---- delete confirmation gate (the safety gap)
    def test_delete_requires_confirmation_then_deletes(self):
        tid = json.loads(tools.create_task("s1", "Temp task"))["task_id"]
        first = json.loads(tools.delete_task("s1", tid))
        self.assertEqual(first["status"], "confirmation_required")
        self.assertEqual(json.loads(tools.list_tasks("s1"))["count"], 1)  # not deleted yet
        second = json.loads(tools.delete_task("s1", tid, confirm=True))
        self.assertEqual(second["status"], "success")
        self.assertEqual(json.loads(tools.list_tasks("s1"))["count"], 0)

    def test_delete_confirm_without_request_rejected(self):
        tid = json.loads(tools.create_task("s1", "Temp task"))["task_id"]
        self.assertEqual(json.loads(tools.delete_task("s1", tid, confirm=True))["status"], "error")

    def test_delete_confirm_wrong_task_rejected(self):
        tid1 = json.loads(tools.create_task("s1", "Task A"))["task_id"]
        tid2 = json.loads(tools.create_task("s1", "Task B"))["task_id"]
        tools.delete_task("s1", tid1)  # stage delete of tid1
        res = json.loads(tools.delete_task("s1", tid2, confirm=True))  # try to sneak-confirm tid2
        self.assertEqual(res["status"], "error")
        self.assertEqual(json.loads(tools.list_tasks("s1"))["count"], 2)  # nothing deleted

    def test_delete_invalid_task_id(self):
        self.assertEqual(json.loads(tools.delete_task("s1", "abc"))["status"], "error")

    def test_delete_nonexistent_task(self):
        self.assertEqual(json.loads(tools.delete_task("s1", 999))["status"], "error")


if __name__ == "__main__":
    unittest.main()
