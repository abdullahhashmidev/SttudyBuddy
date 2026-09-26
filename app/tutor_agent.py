"""
StudyBuddy Tutor Agent Node (Response Synthesizer)
Generates encouraging, formatted response with follow-up suggestions.
"""
 
import json
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage
from app.config import GROQ_API_KEY, DEFAULT_MODEL
from app.logger import log_node_start, log_node_end
from app.memory import AgentState
 
ACTION_INTENTS = {
    "create_task", "manage_task", "plan_study", "create_note",
    "search_notes", "quiz_generate", "quiz_take", "delete_request",
}
 
 
def response_synthesizer_node(state: AgentState) -> dict:
    log_node_start("response_synthesizer", state)
 
    intent = state.get("intent", "general_chat")
    tool_results = state.get("tool_results", [])
    pending_confirmation = state.get("pending_confirmation")
    error_state = state.get("error_state")
    messages = state.get("messages", [])
 
    # If waiting for confirmation, prompt user
    if pending_confirmation:
        action = pending_confirmation.get("action", "")
        log_node_end("response_synthesizer", "Prompted for deletion confirmation")
        return {
            "agent_response": f"⚠️ **Confirmation Required**: Are you sure you want to {action}? Reply 'yes' to confirm or 'no' to cancel.",
            "suggested_followups": ["Yes, proceed", "No, cancel"],
            "is_complete": True
        }
 
    # -------------------------------------------------------------------
    # CRITICAL: never let the LLM claim an action succeeded when nothing
    # actually ran. If the intent implies an action but no tool_results
    # exist (and no error was recorded), the planner could not resolve
    # what to do (e.g. couldn't match a task by name) — be honest about it
    # instead of asking the LLM to "synthesize a friendly response" from
    # an empty context, which invites hallucinated success messages.
    # -------------------------------------------------------------------
    if intent in ACTION_INTENTS and not tool_results and not error_state:
        log_node_end("response_synthesizer", "No tool executed — returning clarification instead of guessing")
        return {
            "agent_response": (
                "I couldn't find a matching item for that request, so I didn't make any changes. "
                "Could you tell me the exact task/note title, or its ID from 'Show my tasks' / "
                "'Show my notes'? I don't want to guess and update the wrong thing."
            ),
            "suggested_followups": ["Show all my tasks", "Show my notes"],
            "is_complete": True
        }
 
    if error_state:
        tool_name = error_state.get("tool", "that")
        error_msg = error_state.get("error", "an unknown error")
        log_node_end("response_synthesizer", f"Reporting tool error for {tool_name}")
        return {
            "agent_response": (
                f"⚠️ I tried to complete that, but the **{tool_name}** step failed ({error_msg}). "
                f"Nothing was changed. Want to try again with more specific details?"
            ),
            "suggested_followups": ["Show all my tasks", "Try again"],
            "is_complete": True
        }
 
    # Build context summary from executed tools
    summary_text = ""
    if tool_results:
        for result in tool_results:
            tool_name = result.get("tool")
            data = result.get("result", {})
 
            if tool_name == "list_tasks":
                tasks = data.get("tasks", [])
                if not tasks:
                    summary_text += "\n📋 No tasks found. Your task list is currently empty."
                else:
                    summary_text += f"\n📋 Found {len(tasks)} task(s):\n"
                    for t in tasks:
                        summary_text += f"  - [{t['task_id']}] {t['title']} (Due: {t.get('deadline', 'No deadline')}) - Status: {t['status']}\n"
 
            elif tool_name == "create_task":
                summary_text += f"\n✅ Task created: {data.get('message')}"
 
            elif tool_name == "update_task":
                summary_text += f"\n✅ Task updated: {data.get('message')}"
 
            elif tool_name == "delete_task":
                summary_text += f"\n🗑️ Task deleted: {data.get('message')}"
 
            elif tool_name == "create_study_session":
                summary_text += f"\n✅ Study session scheduled: {data.get('message')}"
 
            elif tool_name == "create_note":
                summary_text += f"\n✅ Note saved: {data.get('message')}"
 
            elif tool_name == "search_notes":
                notes = data.get("notes", [])
                if not notes:
                    summary_text += "\n🔍 No notes found matching your search."
                else:
                    summary_text += f"\n🔍 Found {len(notes)} note(s):\n"
                    for n in notes[:3]:
                        summary_text += f"  - {n['title']}: {n['content'][:50]}...\n"
 
            elif tool_name == "generate_quiz":
                quiz_data = data.get("quiz", {})
                quiz_id = data.get("quiz_id")
                questions = quiz_data.get("questions", [])
                summary_text += f"\n🧠 Quiz #{quiz_id} Generated with {len(questions)} questions:\n"
                for i, q in enumerate(questions, 1):
                    summary_text += f"\nQ{i}: {q.get('question')}\n"
                    for opt in q.get("options", []):
                        summary_text += f"   {opt}\n"
                summary_text += f"\n(Student can submit answers like: 'Evaluate quiz {quiz_id} with answers q1:B, q2:A, ...')\n"
 
            elif tool_name == "evaluate_quiz":
                score = data.get("score", 0)
                correct = data.get("correct", 0)
                total = data.get("total", 0)
                summary_text += f"\n📊 Quiz Evaluation: Score {score}% ({correct}/{total} correct)\n"
                for res in data.get("results", []):
                    icon = "✅" if res.get("is_correct") else "❌"
                    summary_text += f"{icon} Q: {res.get('question')} | Your answer: {res.get('your_answer')} | Correct: {res.get('correct_answer')}\n"
 
    last_user_msg = messages[-1].content if messages else ""
 
    llm = ChatGroq(model=DEFAULT_MODEL, api_key=GROQ_API_KEY, temperature=0.5)
 
    prompt = f"""You are StudyBuddy, an encouraging academic coach. Synthesize a friendly, clean response for the student.
 
User said: "{last_user_msg}"
Intent: {intent}
Tool Results / System Context:
{summary_text}
 
Formatting Rules:
- Base your response ONLY on the Tool Results / System Context above — never claim an
  action (created, updated, deleted, saved) succeeded unless it is explicitly listed there.
- If a quiz was generated, list each question clearly with its options (A, B, C, D) and tell them how to submit answers.
- If a quiz was evaluated, highlight their score, praise their correct answers, and gently explain mistakes.
- If tasks or notes were processed, format them clearly with bullet points.
- Keep the tone warm, concise, and motivational.
 
Response:"""
 
    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        agent_response = response.content.strip()
    except Exception as e:
        log_node_end("response_synthesizer", f"Error generating response: {str(e)}")
        agent_response = "I've processed your request! Let me know what we should work on next. 📚"
 
    followup_map = {
        "create_task": ["Show all my tasks", "Schedule a study session"],
        "manage_task": ["Add a new task", "Show all my tasks"],
        "plan_study": ["Show all my tasks", "Generate a quiz for this topic"],
        "create_note": ["Search my notes", "Generate a quiz on this note"],
        "search_notes": ["Create a new note", "Show all my tasks"],
        "quiz_generate": ["Evaluate my quiz answers", "Schedule a study session"],
        "quiz_take": ["Generate another quiz", "Save a note on weak areas"],
    }
    followups = followup_map.get(intent, ["Generate a quiz", "Show all my tasks"])
 
    log_node_end("response_synthesizer", "Synthesized final response successfully")
 
    return {
        "agent_response": agent_response,
        "suggested_followups": followups[:2],
        "is_complete": True
    }
 