"""
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
    print(f"\n✅ Initial State Initialized:")
    print(f"   User ID   : {state['user_id']}")
    print(f"   Session ID: {state['session_id']}")
    print(f"   Messages  : {len(state['messages'])} message(s)")
    print(f"   Timestamp : {state['current_timestamp']}")

    # 3. Test SQLite Checkpointer
    checkpointer = get_sqlite_checkpointer()
    print("✅ SQLite Memory Checkpointer verified successfully!")

    print("\n🎉 Step 4 Complete & Ready for LangGraph Agent Nodes!")
