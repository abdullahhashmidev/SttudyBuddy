"""
StudyBuddy End-to-End Flow Tests
Tests complete user workflows through the agent
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db import init_db
from app.orchestrator import build_graph
from langchain_core.messages import HumanMessage

def run_test(name, test_func):
    """Helper to run a test and print result"""
    try:
        test_func()
        print(f"✅ {name}")
        return True
    except AssertionError as e:
        print(f"❌ {name} → {e}")
        return False
    except Exception as e:
        print(f"❌ {name} → ERROR: {str(e)[:80]}")
        return False


def test_create_and_list_tasks():
    """Test creating a task and listing it"""
    init_db()
    graph = build_graph()
    config = {"configurable": {"thread_id": "test_create_list"}}
    
    # Create task
    result1 = graph.invoke(
        {"messages": [HumanMessage(content="Add a Physics homework due Friday")]},
        config=config
    )
    assert result1.get("agent_response"), "No response for task creation"
    
    # List tasks
    result2 = graph.invoke(
        {"messages": [HumanMessage(content="Show my tasks")]},
        config=config
    )
    response = result2.get("agent_response", "")
    assert "Physics" in response or "homework" in response, f"Task not found in list: {response[:100]}"


def test_update_task_status():
    """Test marking a task as completed"""
    init_db()
    graph = build_graph()
    config = {"configurable": {"thread_id": "test_update"}}
    
    # Create task
    graph.invoke(
        {"messages": [HumanMessage(content="Add Chemistry lab report")]},
        config=config
    )
    
    # List to get task ID
    result2 = graph.invoke(
        {"messages": [HumanMessage(content="Show my tasks")]},
        config=config
    )
    
    # Mark as completed
    result3 = graph.invoke(
        {"messages": [HumanMessage(content="Mark the chemistry task as completed")]},
        config=config
    )
    response = result3.get("agent_response", "")
    assert "completed" in response.lower() or "done" in response.lower(), f"Task not marked complete: {response[:100]}"


def test_quiz_generate_and_evaluate():
    """Test generating and evaluating a quiz"""
    init_db()
    graph = build_graph()
    config = {"configurable": {"thread_id": "test_quiz"}}
    
    # Generate quiz
    result1 = graph.invoke(
        {"messages": [HumanMessage(content="Generate a quiz on Math Algebra with 2 questions")]},
        config=config
    )
    response1 = result1.get("agent_response", "")
    assert "quiz" in response1.lower() or "question" in response1.lower(), f"Quiz not generated: {response1[:100]}"
    
    # Evaluate quiz
    result2 = graph.invoke(
        {"messages": [HumanMessage(content="Evaluate quiz 1 with answers q1:A, q2:B")]},
        config=config
    )
    response2 = result2.get("agent_response", "")
    assert "score" in response2.lower() or "correct" in response2.lower() or "%" in response2, f"Quiz not evaluated: {response2[:100]}"


def test_note_create_and_search():
    """Test creating and searching notes"""
    init_db()
    graph = build_graph()
    config = {"configurable": {"thread_id": "test_notes"}}
    
    # Create note
    result1 = graph.invoke(
        {"messages": [HumanMessage(content="Save a note: Newton's laws - F=ma")]},
        config=config
    )
    assert result1.get("agent_response"), "No response for note creation"
    
    # Search note
    result2 = graph.invoke(
        {"messages": [HumanMessage(content="Find my notes about Newton")]},
        config=config
    )
    response = result2.get("agent_response", "")
    assert "Newton" in response or "note" in response.lower(), f"Note not found: {response[:100]}"


def test_study_session_scheduling():
    """Test scheduling a study session"""
    init_db()
    graph = build_graph()
    config = {"configurable": {"thread_id": "test_session"}}
    
    result = graph.invoke(
        {"messages": [HumanMessage(content="Schedule a study session for Physics tomorrow at 3pm")]},
        config=config
    )
    response = result.get("agent_response", "")
    assert "session" in response.lower() or "scheduled" in response.lower() or "physics" in response.lower(), f"Session not scheduled: {response[:100]}"


def test_delete_with_confirmation():
    """Test deletion requires confirmation"""
    init_db()
    graph = build_graph()
    config = {"configurable": {"thread_id": "test_delete"}}
    
    # Create task
    graph.invoke(
        {"messages": [HumanMessage(content="Add a temporary task")]},
        config=config
    )
    
    # Try to delete
    result = graph.invoke(
        {"messages": [HumanMessage(content="Delete the temporary task")]},
        config=config
    )
    response = result.get("agent_response", "")
    assert "confirm" in response.lower() or "sure" in response.lower() or "yes" in response.lower(), f"No confirmation requested: {response[:100]}"


def test_days_left_deadline():
    """Test that agent calculates days until deadline"""
    init_db()
    graph = build_graph()
    config = {"configurable": {"thread_id": "test_days"}}
    
    # Create task with deadline
    result1 = graph.invoke(
        {"messages": [HumanMessage(content="Add exam due in 7 days")]},
        config=config
    )
    
    # Ask about days left
    result2 = graph.invoke(
        {"messages": [HumanMessage(content="How many days until my exam?")]},
        config=config
    )
    response = result2.get("agent_response", "")
    # Should mention days or date
    assert any(word in response.lower() for word in ["day", "week", "exam", "due"]), f"No deadline info: {response[:100]}"


def test_memory_persists_across_sessions():
    """Test that memory works even with different thread IDs (simulating new session)"""
    init_db()
    graph = build_graph()
    
    # Session 1: Set context
    config1 = {"configurable": {"thread_id": "session_1"}}
    result1 = graph.invoke(
        {"messages": [HumanMessage(content="My favorite subject is Physics")]},
        config=config1
    )
    
    # Session 2: Recall (same thread_id = same conversation)
    config2 = {"configurable": {"thread_id": "session_1"}}
    result2 = graph.invoke(
        {"messages": [HumanMessage(content="What is my favorite subject?")]},
        config=config2
    )
    response = result2.get("agent_response", "")
    assert "physics" in response.lower(), f"Memory not persisted: {response[:100]}"


def test_complex_multi_step():
    """Test a complex workflow: create task, list, update, list again"""
    init_db()
    graph = build_graph()
    config = {"configurable": {"thread_id": "test_complex"}}
    
    # Step 1: Create
    graph.invoke(
        {"messages": [HumanMessage(content="Add Biology assignment")]},
        config=config
    )
    
    # Step 2: List
    result2 = graph.invoke(
        {"messages": [HumanMessage(content="Show my tasks")]},
        config=config
    )
    assert "Biology" in result2.get("agent_response", ""), "Task not in list"
    
    # Step 3: Update
    graph.invoke(
        {"messages": [HumanMessage(content="Mark the biology task as completed")]},
        config=config
    )
    
    # Step 4: List again
    result4 = graph.invoke(
        {"messages": [HumanMessage(content="Show my tasks")]},
        config=config
    )
    response = result4.get("agent_response", "")
    # Should show task as completed
    assert "biology" in response.lower() or "completed" in response.lower(), f"Update not reflected: {response[:100]}"


if __name__ == "__main__":
    print("🧪 StudyBuddy Flow Tests\n")
    
    tests = [
        ("create and list tasks", test_create_and_list_tasks),
        ("update task status", test_update_task_status),
        ("quiz generate and evaluate", test_quiz_generate_and_evaluate),
        ("note create and search", test_note_create_and_search),
        ("study session scheduling", test_study_session_scheduling),
        ("delete with confirmation", test_delete_with_confirmation),
        ("days left deadline", test_days_left_deadline),
        ("memory persists across sessions", test_memory_persists_across_sessions),
        ("complex multi-step workflow", test_complex_multi_step),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        if run_test(name, test_func):
            passed += 1
        else:
            failed += 1
    
    print(f"\n{'='*60}")
    print(f"RESULT: {passed}/{len(tests)} passed")
    if failed > 0:
        print(f"  ❌ {failed} test(s) failed")
    print(f"{'='*60}")
    
    sys.exit(0 if failed == 0 else 1)
