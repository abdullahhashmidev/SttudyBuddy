"""
Quick offline-style test for NLU.
Requires GROQ_API_KEY in .env
"""
from app.nlu import classify_intent

TEST_CASES = [
    "I have a calculus midterm on Friday, add it as high priority",
    "Show me all my pending tasks",
    "Delete my English notes",
    "Plan 3 study sessions for Physics this week",
    "I just studied derivatives for 45 minutes",
    "Save a note: lim x->0 sinx/x = 1, subject Calculus",
    "Find my notes about organic chemistry",
    "How many hours did I study this week?",
    "Hello! What can you do?",
    "Make 10 flashcards on the French Revolution",
]

if __name__ == "__main__":
    print("🧠 Testing NLU Intent Classifier\n" + "=" * 50)
    for msg in TEST_CASES:
        result = classify_intent(msg)
        print(f"\n📩  {msg}")
        print(f"    → intent     : {result.intent}")
        print(f"    → confidence : {result.confidence:.2f}")
        print(f"    → entities   : {result.entities}")
        print(f"    → reasoning  : {result.reasoning}")
    print("\n" + "=" * 50)
    print("✅ NLU test complete!")
