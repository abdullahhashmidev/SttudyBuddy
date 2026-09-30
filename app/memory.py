"""
StudyBuddy State Schema & Memory Checkpointer
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
    """Complete LangGraph State Schema"""
    # Conversation History (Reducer: add_messages appends)
    messages: Annotated[list[BaseMessage], add_messages]
    
    # Identifiers
    user_id: str
    session_id: str
    current_timestamp: str
    
    # Intent & Routing
    intent: str
    
    # Execution Planning
    plan: list[dict]
    tool_calls_made: int
    tool_results: Annotated[list[dict], operator.add]
    
    # Human-in-the-loop
    pending_confirmation: Optional[dict]
    
    # Error Management
    error_state: Optional[dict]
    
    # Output
    agent_response: str
    actions_taken: Annotated[list[dict], operator.add]
    suggested_followups: list[str]
    data_modified: Annotated[list[dict], operator.add]
    
    # Loop Control
    loop_count: int
    is_complete: bool
    
    # Memory context (carries forward)
    memory_context: dict


def get_sqlite_checkpointer() -> SqliteSaver:
    """Returns persistent SQLite checkpointer"""
    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        checkpointer = SqliteSaver(conn)
        logger.info(f"🧠 SqliteSaver Checkpointer initialized at: {DB_PATH}")
        return checkpointer
    except Exception as e:
        logger.error(f"Failed to initialize SqliteSaver: {e}")
        raise e


def create_initial_state(user_id: str = "student_42", session_id: str = "sess_001") -> AgentState:
    """Generate fresh initialized AgentState"""
    from datetime import datetime
    return {
        "messages": [],
        "user_id": user_id,
        "session_id": session_id,
        "current_timestamp": datetime.now().isoformat(),
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
        "is_complete": False,
        "memory_context": {}
    }
