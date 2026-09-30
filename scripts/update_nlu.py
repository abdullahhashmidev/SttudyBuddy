import os

nlu_code = '''"""
StudyBuddy NLU / Intent Classifier
Uses Groq (llama-3.3-70b-versatile) to classify user messages into structured intents.
"""

import json
import re
from typing import Literal
from pydantic import BaseModel, Field
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from app.config import GROQ_API_KEY, DEFAULT_MODEL


# ─── Valid Intents (must match LangGraph router) ───────────────────────────
IntentType = Literal[
    "create_task",
    "manage_task",
    "delete_request",
    "plan_study",
    "view_schedule",
    "log_study",
    "create_note",
    "search_notes",
    "flashcard_create",
    "flashcard_review",
    "get_stats",
    "general_chat",
    "unknown"
]


class IntentResult(BaseModel):
    """Structured output from the NLU classifier."""
    intent: IntentType = Field(description="Primary intent of the user message")
    confidence: float = Field(description="Confidence score 0.0-1.0", ge=0.0, le=1.0)
    entities: dict = Field(default_factory=dict, description="Extracted entities: subject, title, deadline, priority, topic, duration, query, etc.")
    reasoning: str = Field(default="", description="Short reason for this classification")


SYSTEM_PROMPT = """You are the Intent Classifier for StudyBuddy, a personal study assistant AI.

Your ONLY job: classify the student's message into EXACTLY one intent and extract key entities.

INTENT CATEGORIES (pick one):
- "create_task"       : Add assignment, homework, exam, to-do, deadline
- "manage_task"       : List, view, update, complete, check-off existing tasks
- "delete_request"    : Delete / remove / cancel any task, note, or session
- "plan_study"        : Create study plan, schedule sessions, Pomodoro blocks, exam prep plan
- "view_schedule"     : Show upcoming study sessions / calendar / timetable
- "log_study"         : Log completed study time, mark session done, "I studied X for Y mins"
- "create_note"       : Save a note, jot down formula, summary, key points
- "search_notes"      : Find / search / recall previously saved notes
- "flashcard_create"  : Generate / make flashcards for a topic
- "flashcard_review"  : Review / quiz / practice flashcards
- "get_stats"         : Progress, study hours, streaks, how am I doing, statistics
- "general_chat"      : Greetings, thanks, what can you do, small talk, help
- "unknown"           : Truly cannot determine

ENTITY EXTRACTION RULES:
- subject: course name (Calculus, Physics, Biology...)
- title: task or note title
- deadline: any date/time expression (keep raw text, e.g. "next Friday", "2025-07-20")
- priority: low | medium | high
- topic: specific topic inside a subject
- duration_minutes: integer if mentioned
- query: search keywords for notes
- session_id / task_id: if user mentions a specific ID

OUTPUT FORMAT (STRICT JSON ONLY — no markdown, no extra text):
{
  "intent": "create_task",
  "confidence": 0.95,
  "entities": {
    "title": "Calculus Midterm",
    "subject": "Calculus",
    "deadline": "next Friday",
    "priority": "high"
  },
  "reasoning": "User wants to add a high-priority exam task with a deadline"
}

IMPORTANT:
- If multiple intents appear, pick the PRIMARY (first/main) one.
- Deletion words (delete, remove, cancel, clear) → ALWAYS "delete_request".
- Never invent entities that are not implied.
- confidence < 0.5 → intent = "unknown"
"""


def _get_llm() -> ChatGroq:
    if not GROQ_API_KEY or GROQ_API_KEY == "your_groq_api_key_here":
        raise ValueError(
            "GROQ_API_KEY missing! Open .env and paste your key from https://console.groq.com"
        )
    return ChatGroq(
        model=DEFAULT_MODEL,
        api_key=GROQ_API_KEY,
        temperature=0.0,
        max_tokens=512,
    )


def _parse_json(text: str) -> dict:
    """Extract JSON even if model wraps it in markdown fences."""
    text = text.strip()
    # Remove ```json ... ``` if present
    fence = re.search(r"```(?:json)?\\s*([\\s\\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    return json.loads(text)


def classify_intent(user_message: str, current_timestamp: str | None = None) -> IntentResult:
    """
    Main entry point — classify a raw user message.
    Returns IntentResult(intent, confidence, entities, reasoning).
    """
    llm = _get_llm()

    extra_context = ""
    if current_timestamp:
        extra_context = f"\\nCurrent datetime for reference: {current_timestamp}"

    messages = [
        SystemMessage(content=SYSTEM_PROMPT + extra_context),
        HumanMessage(content=user_message),
    ]

    try:
        response = llm.invoke(messages)
        raw = response.content
        data = _parse_json(raw)

        # Validate / coerce
        intent = data.get("intent", "unknown")
        valid = {
            "create_task", "manage_task", "delete_request", "plan_study",
            "view_schedule", "log_study", "create_note", "search_notes",
            "flashcard_create", "flashcard_review", "get_stats",
            "general_chat", "unknown"
        }
        if intent not in valid:
            intent = "unknown"

        return IntentResult(
            intent=intent,
            confidence=float(data.get("confidence", 0.5)),
            entities=data.get("entities") or {},
            reasoning=data.get("reasoning") or "",
        )
    except Exception as e:
        # Hard fallback so the agent never crashes
        return IntentResult(
            intent="unknown",
            confidence=0.0,
            entities={},
            reasoning=f"NLU error: {str(e)}",
        )


# Convenience: plain dict (useful inside LangGraph nodes)
def classify_intent_dict(user_message: str, current_timestamp: str | None = None) -> dict:
    result = classify_intent(user_message, current_timestamp)
    return result.model_dump()
'''

test_nlu_code = '''"""
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
    print("🧠 Testing NLU Intent Classifier\\n" + "=" * 50)
    for msg in TEST_CASES:
        result = classify_intent(msg)
        print(f"\\n📩  {msg}")
        print(f"    → intent     : {result.intent}")
        print(f"    → confidence : {result.confidence:.2f}")
        print(f"    → entities   : {result.entities}")
        print(f"    → reasoning  : {result.reasoning}")
    print("\\n" + "=" * 50)
    print("✅ NLU test complete!")
'''

with open("app/nlu.py", "w", encoding="utf-8") as f:
    f.write(nlu_code)
print("✅ Generated: app/nlu.py")

with open("test_nlu.py", "w", encoding="utf-8") as f:
    f.write(test_nlu_code)
print("✅ Generated: test_nlu.py")
print("\\n⚠️  Make sure GROQ_API_KEY is set in .env before running test_nlu.py")