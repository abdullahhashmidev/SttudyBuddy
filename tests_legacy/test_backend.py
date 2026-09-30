"""
StudyBuddy backend smoke test.
Run from the INNER project folder (the one containing app/):  python test_backend.py
"""
import os, sys, json, uuid, importlib, inspect, pkgutil
from datetime import date

TEST_ID = "test_backend_user"
RESULTS = []
STATE = {}


def check(name, fn, *args):
    try:
        detail = fn(*args)
        RESULTS.append((name, "PASS", detail or ""))
        print(f"✅ {name}" + (f"  →  {detail}" if detail else ""))
    except Exception as e:
        RESULTS.append((name, "FAIL", f"{type(e).__name__}: {e}"))
        print(f"❌ {name}  →  {type(e).__name__}: {e}")


# ── environment / imports / config / db ─────────────────────────────
def t_env():
    assert sys.prefix != sys.base_prefix, "venv is NOT active (run: source venv/Scripts/activate)"
    assert os.path.isdir("app"), f"run from the folder that contains app/ (cwd={os.getcwd()})"
    return sys.executable


def t_import(mod):
    importlib.import_module(mod)


def t_config():
    from app.config import GROQ_API_KEY, DEFAULT_MODEL, DB_PATH
    assert GROQ_API_KEY and GROQ_API_KEY != "your_groq_api_key_here", "GROQ_API_KEY missing in .env"
    return f"model={DEFAULT_MODEL} | db={os.path.abspath(DB_PATH)}"


def t_db():
    from app.db import init_db, ensure_student_exists, get_connection
    init_db()
    ensure_student_exists(TEST_ID)
    conn = get_connection()
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    conn.close()
    missing = {"students", "tasks", "study_sessions", "notes"} - tables
    assert not missing, f"missing tables: {missing}"
    return "tables ok"


# ── tools ───────────────────────────────────────────────────────────
def call_tool(name, **kw):
    from app import tools
    fn = getattr(tools, name, None)
    assert fn is not None, f"'{name}' is not defined in app/tools.py"
    out = json.loads(fn(**kw))
    assert out.get("status") == "success", out.get("message")
    return out


def t_create_task():
    out = call_tool("create_task", student_id=TEST_ID, title="Test Physics Chapter 4",
                    subject="Physics", deadline="2026-10-05", priority="high")
    STATE["task_id"] = out["task_id"]
    return f"task_id={out['task_id']}"


def t_list_tasks():
    out = call_tool("list_tasks", student_id=TEST_ID, status="pending")
    assert out["count"] >= 1, "created task not returned"
    return f"count={out['count']}"


def t_update_task():
    call_tool("update_task", student_id=TEST_ID, task_id=STATE["task_id"], deadline="2026-10-06")


def t_session():
    out = call_tool("create_study_session", student_id=TEST_ID, subject="Physics", topic="Kinematics",
                    scheduled_date="2026-09-29 18:00", duration_minutes=45)
    return f"session_id={out['session_id']}"


def t_note():
    call_tool("create_note", student_id=TEST_ID, title="Newton laws", content="F = m * a",
              subject="Physics", tags="mechanics")


def t_search():
    out = call_tool("search_notes", student_id=TEST_ID, query="Newton")
    assert out["count"] >= 1, "note not found"


def t_record():
    call_tool("record_study_session", student_id=TEST_ID, subject="Algebra",
              topic="Quadratics", duration_minutes=45)


def t_quiz_present():
    import app
    found = []
    for m in pkgutil.iter_modules(app.__path__):
        mod = importlib.import_module(f"app.{m.name}")
        for n, _ in inspect.getmembers(mod, inspect.isfunction):
            if "quiz" in n.lower():
                found.append(f"{m.name}.{n}")
    assert found, "no quiz functions found (assignment needs quiz generate + evaluate)"
    return ", ".join(found)


# ── NLU ─────────────────────────────────────────────────────────────
NLU_CASES = [
    ("I have a Math exam next Friday. Make me a study plan.", {"plan_study", "create_task"}),
    ("What should I study today?", {"plan_study", "manage_task", "view_schedule"}),
    ("I studied Algebra for 45 minutes. Record it.", {"log_study"}),
    ("I haven't completed Chapter 3. Move it to tomorrow.", {"manage_task"}),
    ("Give me a quiz on Algebra.", {"quiz_generate", "flashcard_review", "flashcard_create"}),
    ("Show me my progress this week.", {"get_stats"}),
    ("Delete all my English notes", {"delete_request"}),
    ("Hello!", {"general_chat"}),
]


def t_nlu(msg, allowed):
    from app.nlu import classify_intent_dict
    r = classify_intent_dict(msg)
    assert r["intent"] in allowed, (
        f"got '{r['intent']}' ({str(r.get('reasoning'))[:90]}); expected one of {sorted(allowed)}")
    return r["intent"]


# ── planner / tutor nodes ───────────────────────────────────────────
def t_planner():
    from langchain_core.messages import HumanMessage
    from app.memory import create_initial_state
    from app.planner_agent import planner_node
    s = create_initial_state(user_id=TEST_ID)
    s["intent"] = "create_task"
    s["messages"].append(HumanMessage(content="Add a task: Physics Chapter 4 due Monday, high priority"))
    plan = planner_node(s).get("plan")
    assert plan, "planner returned an empty plan (check logs/agent.log)"
    return str([c["tool"] for c in plan])


def t_tutor():
    from langchain_core.messages import HumanMessage
    from app.memory import create_initial_state
    from app.tutor_agent import response_synthesizer_node
    s = create_initial_state(user_id=TEST_ID)
    s["intent"] = "create_task"
    s["messages"].append(HumanMessage(content="Add a task for Physics lab report due Friday"))
    s["tool_results"] = [{"tool": "create_task", "result": {"status": "success", "task_id": 1}}]
    s["actions_taken"] = [{"tool": "create_task", "result": "success"}]
    resp = response_synthesizer_node(s)["agent_response"]
    assert resp and "processed your request" not in resp, "tutor used fallback text (LLM/JSON error, see logs/agent.log)"


# ── full graph ──────────────────────────────────────────────────────
_GRAPH = None


def get_graph():
    global _GRAPH
    if _GRAPH is None:
        from app.orchestrator import build_graph
        _GRAPH = build_graph()
    return _GRAPH


def ask(msg, thread):
    from langchain_core.messages import HumanMessage
    return get_graph().invoke(
        {"messages": [HumanMessage(content=msg)], "user_id": TEST_ID, "session_id": thread,
         "intent": "general_chat", "plan": [], "pending_confirmation": None, "error_state": None,
         "is_complete": False, "tool_calls_made": 0, "loop_count": 0},
        config={"configurable": {"thread_id": thread}})


def task_titles():
    from app.tools import list_tasks
    return [t["title"] for t in json.loads(list_tasks(student_id=TEST_ID))["tasks"]]


def new_thread():
    return f"t_{uuid.uuid4().hex[:6]}"


def t_graph_create():
    r = ask("Add a task: Chemistry homework due next Monday, high priority", new_thread())
    assert r.get("agent_response"), "empty response"
    titles = task_titles()
    assert any("chem" in t.lower() for t in titles), f"task not saved in DB; titles={titles}"
    return "saved in DB"


def t_graph_chat():
    r = ask("Hi! What can you do?", new_thread())
    assert r.get("agent_response"), "empty response"
    assert r.get("tool_calls_made", 0) == 0, "plain chat should not call tools"


def t_graph_delete_guard():
    before = len(task_titles())
    r = ask("Delete all my Chemistry tasks", new_thread())
    assert len(task_titles()) == before, "DATA WAS DELETED WITHOUT CONFIRMATION"
    assert "confirm" in r["agent_response"].lower(), "no confirmation prompt shown"


def t_graph_memory():
    th = new_thread()
    ask("I have a chemistry final on December 15th", th)
    r = ask("How many days until my chemistry final?", th)
    days = (date(date.today().year, 12, 15) - date.today()).days
    assert str(days) in r["agent_response"], f"expected '{days}' in answer; got: {r['agent_response'][:120]}"


def cleanup():
    from app.db import get_connection
    conn = get_connection()
    try:
        for t in ("tasks", "study_sessions", "notes"):
            conn.execute(f"DELETE FROM {t} WHERE student_id = ?", (TEST_ID,))
        conn.execute("DELETE FROM students WHERE student_id = ?", (TEST_ID,))
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    try:
        print("\n── ENVIRONMENT ──")
        check("venv active + correct folder", t_env)
        for m in ["app.config", "app.logger", "app.db", "app.memory", "app.nlu",
                  "app.tools", "app.planner_agent", "app.tutor_agent", "app.orchestrator"]:
            check(f"import {m}", t_import, m)
        check("config (.env key + model + db path)", t_config)
        check("database schema", t_db)

        print("\n── TOOLS ──")
        check("tool: create_task", t_create_task)
        check("tool: list_tasks", t_list_tasks)
        check("tool: update_task", t_update_task)
        check("tool: create_study_session", t_session)
        check("tool: create_note", t_note)
        check("tool: search_notes", t_search)
        check("tool: record_study_session (REQUIRED by assignment)", t_record)
        check("quiz functions exist (REQUIRED by assignment)", t_quiz_present)

        print("\n── NLU (intent classification) ──")
        for msg, allowed in NLU_CASES:
            check(f"nlu: {msg[:45]}", t_nlu, msg, allowed)

        print("\n── PLANNER / TUTOR NODES ──")
        check("planner_node builds a plan", t_planner)
        check("response_synthesizer_node", t_tutor)

        print("\n── FULL GRAPH ──")
        check("graph: create task end-to-end", t_graph_create)
        check("graph: general chat uses no tools", t_graph_chat)
        check("graph: delete needs confirmation", t_graph_delete_guard)
        check("graph: memory across turns", t_graph_memory)
    finally:
        try:
            cleanup()
        except Exception as e:
            print(f"(cleanup skipped: {e})")

    passed = sum(1 for _, s, _ in RESULTS if s == "PASS")
    print("\n" + "=" * 60)
    print(f"RESULT: {passed}/{len(RESULTS)} passed")
    for n, s, d in RESULTS:
        if s == "FAIL":
            print(f"  ❌ {n}: {d}")
    print("Details: logs/agent.log")
    sys.exit(0 if passed == len(RESULTS) else 1)