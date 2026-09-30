from app.db import init_db, ensure_student_exists

if __name__ == "__main__":
    init_db()
    student = ensure_student_exists(
        student_id="student_42",
        name="Abdullah",
        preferred_study_time="evening",
        daily_available_minutes=120
    )
    print("DB initialized. Demo student ready:")
    print(student)