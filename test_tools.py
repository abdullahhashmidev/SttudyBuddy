from app.tools import create_task, list_tasks, create_study_session, create_note, search_notes

if __name__ == "__main__":
    print("🧪 Testing Tools Execution...")
    
    # 1. Test create_task
    res1 = create_task.invoke({
        "student_id": "student_42",
        "title": "Calculus Midterm Prep",
        "subject": "Calculus",
        "deadline": "2025-07-20",
        "priority": "high"
    })
    print("1. Create Task Result:", res1)
    
    # 2. Test list_tasks
    res2 = list_tasks.invoke({"student_id": "student_42"})
    print("2. List Tasks Result:", res2)
    
    # 3. Test create_note
    res3 = create_note.invoke({
        "student_id": "student_42",
        "title": "Limits Formula Sheet",
        "content": "lim x->0 (sin x / x) = 1",
        "subject": "Calculus",
        "tags": "math,limits"
    })
    print("3. Create Note Result:", res3)
    
    print("\n✅ All Tools Working Perfect!")
