import html
import logging
from datetime import datetime

import pandas as pd
import plotly.express as px
import streamlit as st
from langchain_core.messages import HumanMessage

from app.db import init_db
from app.orchestrator import build_graph
from app import ui_services as svc

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("studybuddy")

st.set_page_config(
    page_title="StudyBuddy - AI Study Assistant",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .main-header { font-size: 2.2rem; font-weight: 700; color: #1E88E5; text-align: center; margin-bottom: 1rem; }
    .stButton>button { width: 100%; background-color: #1E88E5; color: white; border-radius: 8px; font-weight: 600; }
    .stButton>button:hover { background-color: #1565C0; }
    .quiz-card { background: #f8f9fa; padding: 1rem; border-radius: 8px; margin: 0.5rem 0; border-left: 4px solid #2196F3; color: #212121; }
    </style>
    """,
    unsafe_allow_html=True,
)

PAGES = ["💬 Chat", "✅ Tasks", "🧠 Quiz", "📝 Notes", "📊 Analytics"]


# ---------------- Cache & Session ----------------
@st.cache_resource(show_spinner=False)
def get_agent_graph():
    init_db()
    return build_graph()


def _new_session_id() -> str:
    return f"web_session_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"


def init_session_state():
    defaults = {
        "messages": [],
        "user_id": "student_42",
        "session_id": _new_session_id(),
        "quiz_submitted": False,
        "quiz_score": 0,
        "quiz_results": [],
        "active_quiz": None,
        "quiz_nonce": 0,
        "task_query": "",
        "note_query": "",
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)


init_session_state()
if "agent_graph" not in st.session_state:
    st.session_state.agent_graph = get_agent_graph()

USER_ID = st.session_state.user_id


# ---------------- Flash messages (shown once, survive reruns) ----------------
def set_flash(level: str, msg: str):
    st.session_state["flash"] = (level, msg)


def show_flash():
    f = st.session_state.pop("flash", None)
    if f:
        getattr(st, f[0])(f[1])


# ---------------- Callbacks (run BEFORE the rerun => no lost clicks) ----------------
def cb_clear_chat():
    st.session_state.messages = []
    st.session_state.session_id = _new_session_id()


def cb_task_search():
    st.session_state.task_query = (st.session_state.get("task_search_input") or "").strip()


def cb_task_clear():
    st.session_state.task_query = ""


def cb_add_task():
    ss = st.session_state
    ok, msg = svc.add_task(
        USER_ID, ss.get("add_task_title"), ss.get("add_task_subject"),
        ss.get("add_task_deadline"), ss.get("add_task_priority", "medium"),
    )
    set_flash("success" if ok else "error", msg)
    if ok:
        ss["add_task_title"] = ""
        ss["add_task_subject"] = ""
        ss["task_query"] = ""  # new task must be visible


def cb_complete_task():
    ss = st.session_state
    tid = ss.get("complete_task_id", "")
    if not tid:
        set_flash("warning", "Pehle task ID select karo.")
        return
    ok, msg = svc.complete_task(USER_ID, tid)
    set_flash("success" if ok else "error", msg)
    if ok:
        ss["complete_task_id"] = ""


def cb_note_search():
    st.session_state.note_query = (st.session_state.get("note_search_input") or "").strip()


def cb_note_clear():
    st.session_state.note_query = ""


def cb_add_note():
    ss = st.session_state
    ok, msg = svc.add_note(USER_ID, ss.get("add_note_title"), ss.get("add_note_subject"), ss.get("add_note_content"))
    set_flash("success" if ok else "error", msg)
    if ok:
        ss["add_note_title"] = ""
        ss["add_note_subject"] = ""
        ss["add_note_content"] = ""
        ss["note_query"] = ""


def _reset_quiz_view():
    ss = st.session_state
    ss.quiz_submitted = False
    ss.quiz_score = 0
    ss.quiz_results = []
    ss.active_quiz = None
    ss.quiz_nonce += 1  # fresh widget keys => old answers never stick


def cb_new_quiz():
    _reset_quiz_view()


def cb_submit_quiz():
    ss = st.session_state
    aq = ss.get("active_quiz")
    if not aq:
        return
    n = ss.quiz_nonce
    picks = [ss.get(f"qz{n}_{i}") for i in range(1, len(aq["questions"]) + 1)]
    if any(p is None for p in picks):
        set_flash("warning", "Sab questions ke answer select karo.")
        return
    ok, msg, res = svc.grade_quiz(USER_ID, aq["quiz_id"], {f"q{i}": p[0] for i, p in enumerate(picks, 1)})
    if not ok:
        set_flash("error", msg)
        return
    ss.quiz_score = round(res["score"])
    ss.quiz_results = res["results"]
    ss.quiz_submitted = True
    ss.active_quiz = None


# ---------------- Agent ----------------
def execute_agent(user_input: str) -> dict:
    config = {"configurable": {"thread_id": st.session_state.session_id}}
    state = {
        "messages": [HumanMessage(content=user_input)],
        "user_id": USER_ID,
        "session_id": st.session_state.session_id,
    }
    try:
        return st.session_state.agent_graph.invoke(state, config=config)
    except Exception as e:
        return {"agent_response": f"⚠️ Error: {e}"}


# ---------------- Sidebar ----------------
with st.sidebar:
    st.markdown("### 📚 StudyBuddy")
    stats = svc.db_stats(USER_ID)
    col1, col2 = st.columns(2)
    col1.metric("📝 Total Tasks", stats["tasks"])
    col1.metric("⏰ Pending Tasks", stats["pending_tasks"])
    col2.metric("📚 Quizzes Taken", stats["quizzes"])
    col2.metric("📖 Notes Saved", stats["notes"])
    st.markdown("---")
    page = st.radio("Navigation", PAGES, label_visibility="collapsed", key="nav_page")

# Page changed => drop every stale search / flash / finished-quiz view
if st.session_state.get("_last_page") != page:
    st.session_state["task_query"] = ""
    st.session_state["note_query"] = ""
    st.session_state.pop("flash", None)
    if st.session_state.quiz_submitted:
        _reset_quiz_view()
    st.session_state["_last_page"] = page


def search_bar(label, placeholder, input_key, form_key, query_key, on_search, on_clear):
    """Search form: input empties after submit, active query shown as a chip with a Clear button."""
    with st.form(form_key, clear_on_submit=True):
        st.text_input(label, placeholder=placeholder, key=input_key)
        st.form_submit_button("🔍 Search", on_click=on_search)
    q = st.session_state.get(query_key, "")
    if q:
        c1, c2 = st.columns([4, 1])
        c1.caption(f"Showing results for: **{q}**")
        c2.button("✖ Clear search", key=f"btn_clear_{query_key}", on_click=on_clear)
    return q


# ---------------- Pages ----------------
if page == "💬 Chat":
    st.markdown('<div class="main-header">💬 Chat with StudyBuddy</div>', unsafe_allow_html=True)
    st.button("🗑️ Clear Chat", key="btn_clear_chat", on_click=cb_clear_chat)
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
    if prompt := st.chat_input("Ask me anything..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                res = execute_agent(prompt)
                st.markdown(res.get("agent_response", "..."))
        st.session_state.messages.append({"role": "assistant", "content": res.get("agent_response", "")})

elif page == "✅ Tasks":
    st.markdown('<div class="main-header">✅ Your Tasks</div>', unsafe_allow_html=True)
    show_flash()

    task_q = search_bar("🔍 Search Tasks", "Search by title or subject...", "task_search_input",
                        "task_search_form", "task_query", cb_task_search, cb_task_clear)

    with st.expander("➕ Add New Task", expanded=False):
        with st.form("add_task_form"):
            st.text_input("Task Title", key="add_task_title")
            st.text_input("Subject", key="add_task_subject")
            st.date_input("Deadline", key="add_task_deadline")
            st.selectbox("Priority", ["low", "medium", "high"], index=1, key="add_task_priority")
            st.form_submit_button("Add Task", on_click=cb_add_task)

    df_tasks = svc.get_tasks_df(USER_ID, task_q)

    if df_tasks.empty:
        st.info("No tasks match your search." if task_q else "No tasks yet. Add one above.")
    else:
        st.dataframe(df_tasks, width="stretch", hide_index=True)
        pending = df_tasks[df_tasks["status"] != "completed"]
        titles = dict(zip(pending["task_id"].astype(str), pending["title"].astype(str)))
        if st.session_state.get("complete_task_id", "") not in [""] + list(titles):
            st.session_state["complete_task_id"] = ""
        if not titles:
            st.info("Sab tasks completed hain 🎉")
        else:
            col1, _ = st.columns(2)
            with col1:
                st.selectbox(
                    "Mark Task Completed (Select ID)",
                    options=[""] + list(titles.keys()),
                    format_func=lambda x: "— select task —" if x == "" else f"#{x} · {titles[x]}",
                    key="complete_task_id",
                )
                st.button("Mark Task Completed", key="btn_mark_task_completed", on_click=cb_complete_task)

elif page == "🧠 Quiz":
    st.markdown('<div class="main-header">🧠 Interactive AI Quiz Center</div>', unsafe_allow_html=True)
    show_flash()
    tab1, tab2 = st.tabs(["🎯 Take Quiz", "📊 Quiz History"])

    with tab1:
        n = st.session_state.quiz_nonce

        if st.session_state.quiz_submitted:
            st.success(f"🎉 Quiz Submitted! Your Score: {st.session_state.quiz_score}%")
            st.markdown("### 📋 Detailed Results")
            for i, r in enumerate(st.session_state.quiz_results, 1):
                icon = "✅" if r["is_correct"] else "❌"
                expl = f"<br><i>{html.escape(r['explanation'])}</i>" if r.get("explanation") else ""
                st.markdown(
                    f'<div class="quiz-card"><b>Q{i}:</b> {html.escape(r["question"])}<br>'
                    f'{icon} Your Answer: <b>{html.escape(str(r["your_answer"]))}</b> | '
                    f'Correct: <b>{html.escape(str(r["correct_answer"]))}</b>{expl}</div>',
                    unsafe_allow_html=True,
                )
            st.button("🔄 Take Another Quiz", key="btn_take_another_quiz", on_click=cb_new_quiz)

        elif st.session_state.active_quiz is None:
            st.markdown("### 🎯 Generate a New Quiz")
            c1, c2, c3 = st.columns([2, 2, 1])
            subject = c1.text_input("Subject", value="AI", key=f"quiz_subject_{n}")
            topic = c2.text_input("Topic", value="Agentic AI", key=f"quiz_topic_{n}")
            num_q = c3.number_input("Questions", min_value=3, max_value=10, value=5, step=1, key=f"quiz_num_{n}")
            if st.button("🚀 Generate Quiz", key=f"btn_generate_quiz_{n}"):
                with st.spinner("AI quiz bana raha hai..."):
                    ok, msg, quiz = svc.create_quiz(USER_ID, subject, topic, int(num_q))
                if ok:
                    st.session_state.active_quiz = quiz
                    st.rerun()
                else:
                    st.error(msg)

        else:
            aq = st.session_state.active_quiz
            st.markdown("### Answer Quiz Questions Below:")
            with st.form(f"quiz_form_{n}"):
                for i, q in enumerate(aq["questions"], 1):
                    st.radio(f"Q{i}: {q['question']}", q["options"], index=None, key=f"qz{n}_{i}")
                st.form_submit_button("Submit Quiz Answers", on_click=cb_submit_quiz)
            st.button("❌ Cancel Quiz", key=f"btn_cancel_quiz_{n}", on_click=cb_new_quiz)

    with tab2:
        df_qh = svc.get_quiz_history_df(USER_ID)
        if df_qh.empty:
            st.info("No quiz attempts yet.")
        else:
            st.dataframe(df_qh, width="stretch", hide_index=True)

elif page == "📝 Notes":
    st.markdown('<div class="main-header">📝 Study Notes</div>', unsafe_allow_html=True)
    show_flash()

    note_q = search_bar("🔍 Search Notes", "Search by title, subject or content...", "note_search_input",
                        "note_search_form", "note_query", cb_note_search, cb_note_clear)

    with st.expander("➕ Create New Note", expanded=False):
        with st.form("add_note_form"):
            st.text_input("Note Title", key="add_note_title")
            st.text_input("Subject", key="add_note_subject")
            st.text_area("Content", key="add_note_content")
            st.form_submit_button("Save Note", on_click=cb_add_note)

    df_notes = svc.get_notes_df(USER_ID, note_q)

    if df_notes.empty:
        st.info("No notes match your search." if note_q else "No notes yet. Create one above.")
    else:
        for _, row in df_notes.iterrows():
            with st.expander(f"📖 {row['title']} ({row['subject'] or 'General'})"):
                st.write(row["content"])
                st.caption(f"Created at: {row['created_at']}")

elif page == "📊 Analytics":
    st.markdown('<div class="main-header">📊 Study Analytics</div>', unsafe_allow_html=True)
    stats = svc.db_stats(USER_ID)
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Tasks", stats["tasks"])
    c2.metric("Pending Tasks", stats["pending_tasks"])
    c3.metric("Quizzes Taken", stats["quizzes"])

    df_tasks = svc.get_tasks_df(USER_ID)
    if df_tasks.empty:
        st.info("Analytics ke liye pehle tasks add karo.")
    else:
        st.subheader("Task Status Distribution")
        sc = df_tasks["status"].value_counts().reset_index()
        sc.columns = ["status", "count"]
        st.plotly_chart(px.pie(sc, values="count", names="status", hole=0.4), width="stretch")

    df_qh = svc.get_quiz_history_df(USER_ID)
    if not df_qh.empty:
        st.subheader("Quiz Scores Over Time")
        dfp = df_qh.sort_values("attempt_date")
        st.plotly_chart(px.bar(dfp, x="attempt_date", y="score", hover_data=["subject", "topic"]), width="stretch")
