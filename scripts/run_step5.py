import os
import json
import re

# ─── 1. Write app/planner_agent.py ──────────────────────────────────────────
planner_code = '''"""
StudyBuddy Planner Agent Node
Generates step-by-step tool execution plans and handles confirmation triggers for destructive actions.
"""

import json
import re
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from app.config import GROQ_API_KEY, DEFAULT_MODEL
from app.logger import log_node_start, log_node_end, logger
from app.memory import AgentState


PLANNER_SYSTEM_PROMPT = """You are the planning engine for StudyBuddy, a personal study assistant.

Given the user's message, classified intent, and extracted entities, produce a JSON plan: an ordered list of tool calls needed to fulfill the request.

Your output MUST be a JSON object matching this schema:
{{
  "plan": [
    {{"tool": "<tool_name>", "args": {{<arg_name>: <value>, ...}}}}
  ],
  "pending_confirmation": null | {{"action": "<description>", "details": {{"tool": "<tool_name>", "args": {{...}}}}}}
}}

RULES:
1. Available tools:
   - create_task(student_id, title, subject, deadline, priority)
   - list_tasks(student_id, status, subject)
   - create_study_session(student_id, subject, topic, scheduled_date, duration_minutes)
   - create_note(student_id, title, content, subject, tags)
   - search_notes(student_id, query, subject)

2. Absolute student_id = "{student_id}". Always pass this in tool arguments.
3. Max tool budget per turn is 7. Current tool_calls_made = {tool_calls_made}.
4. If intent is "delete_request", set "pending_confirmation" with delete action details and leave "plan" empty [].
5. Respond with STRICT JSON ONLY (no markdown fences, no conversational text).
"""


def _get_llm():
    if not GROQ_API_KEY or GROQ_API_KEY == "your_groq_api_key_here":
        raise ValueError("GROQ_API_KEY is missing or invalid in .env file!")
    return ChatGroq(model=DEFAULT_MODEL, api_key=GROQ_API_KEY, temperature=0.0)


def planner_node(state: AgentState) -> dict:
    log_node_start("planner", state)

    intent = state.get("intent", "general_chat")
    user_id = state.get("user_id", "student_42")
    tool_calls_made = state.get("tool_calls_made", 0)

    if intent == "delete_request":
        pending = {
            "action": "delete_data",
            "details": {"message": "User requested data deletion."}
        }
        log_node_end("planner", "Set pending_confirmation for delete_request")
        return {"plan": [], "pending_confirmation": pending}

    if intent in ["general_chat", "unknown"]:
        log_node_end("planner", "No tools required for general chat")
        return {"plan": [], "pending_confirmation": None}

    try:
        llm = _get_llm()
        sys_msg = PLANNER_SYSTEM_PROMPT.format(
            student_id=user_id,
            tool_calls_made=tool_calls_made
        )

        last_user_msg = ""
        for msg in reversed(state.get("messages", [])):
            if getattr(msg, "type", "") == "human" or hasattr(msg, "content"):
                last_user_msg = msg.content
                break

        prompt_content = f"Intent: {intent}\\nUser Request: {last_user_msg}"

        res = llm.invoke([SystemMessage(content=sys_msg), HumanMessage(content=prompt_content)])
        raw_text = res.content.strip()

        if "```" in raw_text:
            match = re.search(r"```(?:json)?\\s*([\\s\\S]*?)```", raw_text)
            if match:
                raw_text = match.group(1).strip()

        data = json.loads(raw_text)
        plan = data.get("plan", [])
        pending = data.get("pending_confirmation", None)

        log_node_end("planner", f"Generated plan with {len(plan)} tool call(s)")
        return {"plan": plan, "pending_confirmation": pending}

    except Exception as e:
        logger.error(f"Planner error: {e}")
        return {"plan": [], "pending_confirmation": None}
'''

# ─── 2. Write app/tutor_agent.py ─────────────────────────────────────────────
tutor_code = '''"""
StudyBuddy Tutor Agent Node (Response Synthesizer)
Generates encouraging, formatted response with follow-up suggestions.
"""

import json
import re
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from app.config import GROQ_API_KEY, DEFAULT_MODEL
from app.logger import log_node_start, log_node_end, logger
from app.memory import AgentState


TUTOR_SYSTEM_PROMPT = """You are StudyBuddy, a friendly and encouraging personal study assistant.
You speak like a smart, supportive upperclassman academic coach.

Your Task:
Synthesize a clear, helpful final response for the student based on the conversation history, intent, and tool execution results.

Tone & Persona Rules:
- Friendly, encouraging, and concise.
- Use clean formatting, bold headers, and bullet points.
- Use emojis lightly (📅, ✅, 📝, 💪, 📊).
- Never fabricate data or claim actions that were not actually performed.
- Never write entire homework/essay solutions.

OUTPUT FORMAT (STRICT JSON ONLY):
{
  "agent_response": "<your friendly formatted markdown response>",
  "suggested_followups": ["<suggestion 1>", "<suggestion 2>"]
}
"""


def _get_llm():
    if not GROQ_API_KEY or GROQ_API_KEY == "your_groq_api_key_here":
        raise ValueError("GROQ_API_KEY is missing or invalid in .env file!")
    return ChatGroq(model=DEFAULT_MODEL, api_key=GROQ_API_KEY, temperature=0.3)


def response_synthesizer_node(state: AgentState) -> dict:
    log_node_start("response_synthesizer", state)

    intent = state.get("intent", "general_chat")
    tool_results = state.get("tool_results", [])
    actions_taken = state.get("actions_taken", [])
    
    if state.get("pending_confirmation"):
        confirm_text = "⚠️ **Action Required**: You requested a deletion. Are you sure you want me to proceed and delete this item? Please reply 'yes' to confirm or 'no' to cancel."
        ai_msg = AIMessage(content=confirm_text)
        log_node_end("response_synthesizer", "Prompted for deletion confirmation")
        return {
            "agent_response": confirm_text,
            "suggested_followups": ["Yes, proceed with deletion", "No, cancel deletion"],
            "messages": [ai_msg]
        }

    try:
        llm = _get_llm()
        context_summary = f"""
Intent: {intent}
Actions Taken: {actions_taken}
Tool Execution Results: {tool_results}
"""

        messages = [SystemMessage(content=TUTOR_SYSTEM_PROMPT)]
        for m in state.get("messages", [])[-5:]:
            messages.append(m)

        messages.append(HumanMessage(content=f"Context and Tool Outputs:\\n{context_summary}\\nSynthesize final user response now."))

        res = llm.invoke(messages)
        raw_text = res.content.strip()

        if "```" in raw_text:
            match = re.search(r"```(?:json)?\\s*([\\s\\S]*?)```", raw_text)
            if match:
                raw_text = match.group(1).strip()

        data = json.loads(raw_text)
        response_text = data.get("agent_response", "I'm all set! Let me know if you need anything else.")
        followups = data.get("suggested_followups", [])

        ai_msg = AIMessage(content=response_text)
        log_node_end("response_synthesizer", "Synthesized final response successfully")

        return {
            "agent_response": response_text,
            "suggested_followups": followups,
            "messages": [ai_msg]
        }

    except Exception as e:
        logger.error(f"Response Synthesizer error: {e}")
        fallback_text = "I've processed your request! Let me know what we should work on next."
        return {
            "agent_response": fallback_text,
            "suggested_followups": [],
            "messages": [AIMessage(content=fallback_text)]
        }
'''

# Save Files
with open("app/planner_agent.py", "w", encoding="utf-8") as f:
    f.write(planner_code)
print("✅ Created: app/planner_agent.py")

with open("app/tutor_agent.py", "w", encoding="utf-8") as f:
    f.write(tutor_code)
print("✅ Created: app/tutor_agent.py")

# Execute Verification Test Immediately
print("\n🧪 Running Step 5 Verification Test...")
from app.memory import create_initial_state
from app.planner_agent import planner_node
from app.tutor_agent import response_synthesizer_node
from langchain_core.messages import HumanMessage

# Test 1: Planning for create_task intent
state = create_initial_state()
state["intent"] = "create_task"
state["messages"].append(HumanMessage(content="Add a task for Physics lab report due Friday"))

plan_output = planner_node(state)
print("\n1. Planner Node Output:")
print("   Plan:", plan_output.get("plan"))
print("   Pending Confirmation:", plan_output.get("pending_confirmation"))

# Test 2: Tutor Synthesizer
state["tool_results"] = [{
    "tool": "create_task",
    "result": {"status": "success", "task_id": 10, "message": "Task 'Physics lab report' created."}
}]
state["actions_taken"] = [{"tool": "create_task", "result": "success"}]

tutor_output = response_synthesizer_node(state)
print("\n2. Tutor Node Output:")
print("   Response:\n", tutor_output.get("agent_response"))
print("\n   Followups:", tutor_output.get("suggested_followups"))

print("\n🎉 Step 5 Complete & Ready for Step 6 (Orchestrator Assembly)!")