"""
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
