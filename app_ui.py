"""
StudyBuddy Streamlit Web UI
Production-ready interface — caching, error handling, lightweight architecture.
"""

import logging
from datetime import datetime

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from langchain_core.messages import HumanMessage

from app.db import init_db, get_connection
from app.orchestrator import build_graph

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("studybuddy")

st.set_page_config(
    page_title="StudyBuddy - AI Study Assistant",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .main-header { font-size: 2.5rem; font-weight: 700; color: #1E88E5; text-align: center; margin-bottom: 2rem; }
    .metric-card { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 1.5rem; border-radius: 10px; color: white; text-align: center; }
    .stButton>button { width: 100%; background-color: #1E88E5; color: white; border-radius: 8px; padding: 0.5rem 1rem; font-weight: 600; }
    .stButton>button:hover { background-color: #1565C0; }
    .success-box { background-color: #E8F5E9; border-left: 4px solid #4CAF50; padding: 1rem; border-radius: 4px; margin: 1rem 0; }
    .error-box { background-color: #FFEBEE; border-left: 4px solid #F44336; padding: 1rem; border-radius: 4px; margin: 1rem 0; }
    .quiz-question { background-color: #F5F5F5; padding: 1.5rem; border-radius: 8px; margin: 1rem 0; border-left: 4px solid #2196F3; }
</style>
""", unsafe_allow_html=True)

@st.cache_resource(show_spinner=False)
def get_agent_graph():
    init_db()
    logger.info("Building agent graph (cache miss)")
    return build_graph()

def init_session_state() -> None:
    defaults = {
        "messages": [],
        "user_id": "student_42",
        "session_id": f"web_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "current_quiz": None,
    }
    for key, val in defaults.items():
        st.session_state.setdefault(key, val)

init_session_state()
if "agent_graph" not in st.session_state:
    st.session_state.agent_graph = get_agent_graph()

USER_ID = st.session_state.user_id

@st.cache_data(ttl=15, show_spinner=False)
def get_database_stats(user_id: str) -> dict:
    conn = get_connection()
    try:
        q = lambda sql, *p: conn.execute(sql, p).fetchone()[0]
        return {
            "tasks": q("SELECT COUNT(*) FROM tasks WHERE student_id = ?", user_id),
            "sessions": q("SELECT COUNT(*) FROM study_sessions WHERE student_id = ?", user_id),
            "notes": q("SELECT COUNT(*) FROM notes WHERE student_id = ?", user_id),
            "quizzes": q("SELECT COUNT(*) FROM quizzes WHERE student_id = ?", user_id),
            "pending_tasks": q('SELECT COUNT(*) FROM tasks WHERE student_id = ? AND status = "pending"', user_id),
        }
    except Exception:
        logger.exception("Failed to load stats")
        return {"tasks": 0, "sessions": 0, "notes": 0, "quizzes": 0, "pending_tasks": 0}
    finally:
        conn.close()

@st.cache_data(ttl=15, show_spinner=False)
def get_tasks_dataframe(user_id: str) -> pd.DataFrame:
    conn = get_connection()
    try:
        return pd.read_sql_query(
            """SELECT task_id, title, subject, deadline, priority, status, created_at
               FROM tasks WHERE student_id = ? ORDER BY created_at DESC""",
            conn, params=(user_id,),
        )
    finally:
        conn.close()

@st.cache_data(ttl=15, show_spinner=False)
def get_quiz_history(user_id: str) -> pd.DataFrame:
    conn = get_connection()
    try:
        return pd.read_sql_query(
            """SELECT qa.attempt_id, q.subject, q.topic, qa.score, qa.attempt_date
               FROM quiz_attempts qa JOIN quizzes q ON qa.quiz_id = q.quiz_id
               WHERE qa.student_id = ? ORDER BY qa.attempt_date DESC""",
            conn, params=(user_id,),
        )
    finally:
        conn.close()

@st.cache_data(ttl=15, show_spinner=False)
def get_notes_dataframe(user_id: str) -> pd.DataFrame:
    conn = get_connection()
    try:
        return pd.read_sql_query(
            "SELECT * FROM notes WHERE student_id = ? ORDER BY created_at DESC",
            conn, params=(user_id,),
        )
    finally:
        conn.close()

def invalidate_caches() -> None:
    get_database_stats.clear()
    get_tasks_dataframe.clear()
    get_quiz_history.clear()
    get_notes_dataframe.clear()

def execute_agent(user_input: str) -> dict:
    config = {"configurable": {"thread_id": st.session_state.session_id}}
    state_update = {
        "messages": [HumanMessage(content=user_input)],
        "user_id": USER_ID,
        "session_id": st.session_state.session_id,
        "intent": "general_chat",
        "plan": [],
        "pending_confirmation": None,
        "error_state": None,
        "is_complete": False,
        "tool_calls_made": 0,
    }
    try:
        result = st.session_state.agent_graph.invoke(state_update, config=config)
        invalidate_caches()
        return result
    except Exception as e:
        logger.exception("Agent execution failed")
        return {"agent_response": f"⚠️ Something went wrong: {e}", "tool_results": []}

with st.sidebar:
    st.markdown("### 📚 StudyBuddy")
    st.markdown("---")
    stats = get_database_stats(USER_ID)
    col1, col2 = st.columns(2)
    with col1:
        st.metric("📝 Total Tasks", stats["tasks"])
        st.metric("📚 Quizzes Taken", stats["quizzes"])
    with col2:
        st.metric("⏰ Pending Tasks", stats["pending_tasks"])
        st.metric("📖 Notes Saved", stats["notes"])
    st.markdown("---")
    st.markdown("### 🧭 Navigation")
    page = st.radio("Select Page", ["💬 Chat", "✅ Tasks", "🧠 Quiz", "📝 Notes", "📊 Analytics"], label_visibility="collapsed")
    st.markdown("---")
    st.markdown(f"**Student ID:** `{st.session_state.user_id}`")
