"""
StudyBuddy CLI
"""

from app.db import init_db
from app.orchestrator import build_graph
from langchain_core.messages import HumanMessage

def main():
    init_db()
    graph = build_graph()
    
    # CRITICAL: Use consistent thread_id for memory persistence
    THREAD_ID = "student_42_session_main"
    config = {"configurable": {"thread_id": THREAD_ID}}

    print("📚 StudyBuddy CLI — type 'exit' to quit\n")

    while True:
        user_input = input("You: ").strip()
        if user_input.lower() in ("exit", "quit"):
            print("👋 Bye! Keep studying!")
            break
        if not user_input:
            continue

        # Only pass new message - checkpointer handles history
        state_update = {
            "messages": [HumanMessage(content=user_input)],
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
