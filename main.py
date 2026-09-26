"""
StudyBuddy CLI
"""

from app.db import init_db
from app.orchestrator import build_graph
from langchain_core.messages import HumanMessage

def main():
    init_db()
    graph = build_graph()
    config = {"configurable": {"thread_id": "fresh_session_001"}}  # ✅ Changed

    print("📚 StudyBuddy CLI — type 'exit' to quit\n")

    while True:
        user_input = input("You: ").strip()
        if user_input.lower() in ("exit", "quit"):
            print("👋 Bye! Keep studying!")
            break
        if not user_input:
            continue

        state_update = {
            "messages": [HumanMessage(content=user_input)],
            "user_id": "student_42",
            "session_id": "student_42_session",
            "intent": "general_chat",
            "plan": [],
            "pending_confirmation": None,
            "error_state": None,
            "is_complete": False,
            "tool_calls_made": 0,  # ✅ Added
        }

        result = graph.invoke(state_update, config=config)
        print(f"\nStudyBuddy: {result.get('agent_response')}\n")

        followups = result.get("suggested_followups", [])
        if followups:
            print("💡 You could also ask:")
            for f in followups:
                print(f"   - {f}")
            print()

if __name__ == "__main__":
    main()