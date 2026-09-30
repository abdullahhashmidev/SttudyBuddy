import os

# ─── 1. app/logger.py CODE ──────────────────────────────────────────────────
logger_code = '''"""
StudyBuddy System Logger
Provides structured logging for Agent Node transitions, Tool calls, Errors, and Memory updates.
"""

import logging
import os
from pathlib import Path

# Create logs directory
LOGS_DIR = Path("logs")
LOGS_DIR.mkdir(exist_ok=True)
LOG_FILE = LOGS_DIR / "agent.log"

# Configure Logging
logger = logging.getLogger("StudyBuddy")
logger.setLevel(logging.INFO)

if not logger.handlers:
    # Console Handler
    c_handler = logging.StreamHandler()
    c_handler.setLevel(logging.INFO)
    c_format = logging.Formatter('🤖 [%(levelname)s] %(asctime)s - %(message)s', datefmt='%H:%M:%S')
    c_handler.setFormatter(c_format)
    logger.addHandler(c_handler)

    # File Handler
    f_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
    f_handler.setLevel(logging.DEBUG)
    f_format = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s (%(filename)s:%(lineno)d): %(message)s')
    f_handler.setFormatter(f_format)
    logger.addHandler(f_handler)


def log_node_start(node_name: str, state: dict):
    logger.info(f"▶ ENTERING NODE: [{node_name}] | Intent: {state.get('intent', 'N/A')} | Loop: {state.get('loop_count', 0)}")


def log_node_end(node_name: str, summary: str):
    logger.info(f"✔ COMPLETED NODE: [{node_name}] -> {summary}")


def log_tool_call(tool_name: str, args: dict):
    logger.info(f"🛠 EXECUTING TOOL: [{tool_name}] | Args: {args}")


def log_tool_result(tool_name: str, success: bool, result_summary: str):
    status = "SUCCESS" if success else "FAILED"
    logger.info(f"  └─ TOOL RESULT [{tool_name}]: {status} | {result_summary}")


def log_error(context: str, error: Exception | str):
    logger.error(f"❌ ERROR in [{context}]: {str(error)}")
'''

# ─── 2. app/memory.py CODE ──────────────────────────────────────────────────
memory_code = '''"""
StudyBuddy State Schema & Memory Checkpointer
Defines the LangGraph AgentState TypedDict and persistent SQLite checkpointer setup.
"""

import sqlite3
import operator
from typing import Annotated, TypedDict, Optional, Any
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from langgraph.checkpoint.sqlite import SqliteSaver
from app.config import DB_PATH
from app.logger import logger


class AgentState(TypedDict):
    """
    Complete LangGraph State Schema for StudyBuddy Agent.
    Exact match with Section 4 Architecture Specification.
    """
    # Conversation History (Reducer: add_messages appends messages)
    messages: Annotated[list[BaseMessage], add_messages]
    
    # Identifiers & Context
    user_id: str
    session_id: str
    current_timestamp: str
    
    # Intent & Routing
    intent: str
    
    # Execution Planning
    plan: list[dict]                        # Form: [{"tool": str, "args": dict}]
    tool_calls_made: int                    # Max 7 enforced
    tool_results: Annotated[list[dict], operator.add]  # Accumulated outputs
    
    # Human-In-The-Loop Safety Guardrail
    pending_confirmation: Optional[dict]    # Set on delete/destructive actions
    
    # Error Management
    error_state: Optional[dict]             # Form: {"tool": str, "error": str, "retry_count": int}
    
    # Output Synthesis
    agent_response: str
    actions_taken: Annotated[list[dict], operator.add]
    suggested_followups: list[str]
    data_modified: Annotated[list[dict], operator.add]
    
    # Loop Control
    loop_count: int                         # Max 4 loops enforced
    is_complete: bool                       # Graph termination flag


def get_sqlite_checkpointer() -> SqliteSaver:
    """
    Returns a persistent SQLite checkpointer for LangGraph Memory across turns.
    Saves graph execution state into studybuddy.db.
    """
    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        checkpointer = SqliteSaver(conn)
        logger.info(f"🧠 SqliteSaver Checkpointer initialized at: {DB_PATH}")
        return checkpointer
    except Exception as e:
        logger.error(f"Failed to initialize SqliteSaver: {e}")
        raise e


def create_initial_state(user_id: str = "student_42", session_id: str = "sess_001", current_timestamp: str = None) -> AgentState:
    """
    Helper function to generate a fresh, initialized AgentState.
    """
    from datetime import datetime
    if not current_timestamp:
        current_timestamp = datetime.now().isoformat()

    return {
        "messages": [],
        "user_id": user_id,
        "session_id": session_id,
        "current_timestamp": current_timestamp,
        "intent": "general_chat",
        "plan": [],
        "tool_calls_made": 0,
        "tool_results": [],
        "pending_confirmation": None,
        "error_state": None,
        "agent_response": "",
        "actions_taken": [],
        "suggested_followups": [],
        "data_modified": [],
        "loop_count": 0,
        "is_complete": False
    }
'''

# ─── 3. test_step4.py CODE ──────────────────────────────────────────────────
test_code = '''"""
Verification script for Step 4 (Logger + Memory/State)
"""
from app.logger import logger, log_node_start, log_node_end, log_tool_call, log_tool_result
from app.memory import AgentState, create_initial_state, get_sqlite_checkpointer
from langchain_core.messages import HumanMessage

if __name__ == "__main__":
    print("🧪 Testing Step 4: Logging & Memory State...")

    # 1. Test Logger
    log_node_start("router", {"intent": "create_task", "loop_count": 0})
    log_tool_call("create_task", {"title": "Math Homework"})
    log_tool_result("create_task", True, "Task ID 1 Created")
    log_node_end("router", "Intent classified successfully")

    # 2. Test Initial State Creation
    state = create_initial_state(user_id="student_42", session_id="test_sess_101")
    state["messages"].append(HumanMessage(content="Hello StudyBuddy!"))
    print(f"\\n✅ Initial State Initialized:")
    print(f"   User ID   : {state['user_id']}")
    print(f"   Session ID: {state['session_id']}")
    print(f"   Messages  : {len(state['messages'])} message(s)")
    print(f"   Timestamp : {state['current_timestamp']}")

    # 3. Test SQLite Checkpointer
    checkpointer = get_sqlite_checkpointer()
    print("✅ SQLite Memory Checkpointer verified successfully!")

    print("\\n🎉 Step 4 Complete & Ready for LangGraph Agent Nodes!")
'''

with open("app/logger.py", "w", encoding="utf-8") as f:
    f.write(logger_code)
print("✅ Generated: app/logger.py")

with open("app/memory.py", "w", encoding="utf-8") as f:
    f.write(memory_code)
print("✅ Generated: app/memory.py")

with open("test_step4.py", "w", encoding="utf-8") as f:
    f.write(test_code)
print("✅ Generated: test_step4.py")