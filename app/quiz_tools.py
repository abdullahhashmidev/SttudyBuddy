"""StudyBuddy Quiz Tools"""
import json
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage
from app.config import GROQ_API_KEY, DEFAULT_MODEL
from app.db import get_connection, ensure_student_exists

def generate_quiz(student_id: str, subject: str, topic: str, num_questions: int = 5) -> str:
    ensure_student_exists(student_id)
    llm = ChatGroq(model=DEFAULT_MODEL, api_key=GROQ_API_KEY, temperature=0.7)
    prompt = f"""Generate a {num_questions}-question multiple choice quiz on {subject} - {topic}.
Return ONLY valid JSON: {{"questions": [{{"question": "...", "options": ["A)", "B)", "C)", "D)"], "correct_answer": "B", "explanation": "..."}}]}}"""
    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        raw = response.content.strip().replace("```json", "").replace("```", "").strip()
        quiz_data = json.loads(raw)
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO quizzes (student_id, subject, topic, questions) VALUES (?, ?, ?, ?)",
                      (student_id, subject, topic, json.dumps(quiz_data)))
        conn.commit()
        quiz_id = cursor.lastrowid
        conn.close()
        return json.dumps({"status": "success", "quiz_id": quiz_id, "quiz": quiz_data, 
                          "message": f"Generated quiz on {subject} - {topic}"})
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})

def evaluate_quiz(student_id: str, quiz_id: int, answers: dict) -> str:
    ensure_student_exists(student_id)
    conn = get_connection()
    try:
        quiz_row = conn.execute("SELECT * FROM quizzes WHERE quiz_id = ? AND student_id = ?", (quiz_id, student_id)).fetchone()
        if not quiz_row:
            return json.dumps({"status": "error", "message": "Quiz not found"})
        quiz_data = json.loads(quiz_row["questions"])
        questions = quiz_data["questions"]
        correct = 0
        results = []
        for i, q in enumerate(questions, 1):
            user_answer = answers.get(f"q{i}", "").strip().upper()
            is_correct = (user_answer == q["correct_answer"].strip().upper())
            if is_correct:
                correct += 1
            results.append({"question": q["question"], "your_answer": user_answer, "correct_answer": q["correct_answer"], "is_correct": is_correct})
        score = (correct / len(questions) * 100) if questions else 0
        cursor = conn.cursor()
        cursor.execute("INSERT INTO quiz_attempts (quiz_id, student_id, answers, score, weak_areas) VALUES (?, ?, ?, ?, ?)",
                      (quiz_id, student_id, json.dumps(answers), score, "[]"))
        conn.commit()
        return json.dumps({"status": "success", "score": round(score, 1), "correct": correct, "total": len(questions), "results": results})
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})
    finally:
        conn.close()
