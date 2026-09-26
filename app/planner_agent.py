"""
StudyBuddy Planner Agent
Converts user intent + context into a concrete execution plan (list of tool calls).
"""
 
import json
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from app.config import GROQ_API_KEY, DEFAULT_MODEL
from app.memory import AgentState
from app.logger import log_node_start, log_node_end
from app import tools as tool_module
 
PLANNER_SYSTEM_PROMPT = """You are the Planner for StudyBuddy, a personal study assistant.
 
Your job: Convert the student's request into a structured execution plan.
 
AVAILABLE TOOLS:
- create_task(student_id, title, subject?, deadline?, priority?) -> Creates assignment/task
- list_tasks(student_id, status?, subject?) -> Lists tasks (status: 'pending', 'completed', or None)
- update_task(student_id, task_id, status?, deadline?, priority?) -> Updates task fields
- delete_task(student_id, task_id) -> Deletes task (REQUIRES USER CONFIRMATION FIRST)
- create_study_session(student_id, subject, topic, scheduled_date, duration_minutes?) -> Schedules study block
- create_note(student_id, title, content, subject?, tags?) -> Saves study note (tags: comma-separated string)
- search_notes(student_id, query?, subject?) -> Searches notes
- generate_quiz(student_id, subject, topic, num_questions?) -> Generates AI quiz (default 5 questions)
- evaluate_quiz(student_id, quiz_id, answers) -> Evaluates quiz answers, e.g. answers={"q1": "B", "q2": "A"}
 
RESOLVING TASK REFERENCES BY NAME:
The student's CURRENT TASKS (with their real task_id) are provided below in CURRENT CONTEXT.
When the student refers to a task by name/subject/description instead of an ID
(e.g. "mark the physics task as completed", "delete my chemistry homework"),
you MUST find the matching task in that list and use its exact task_id.
If NO task in the list plausibly matches what the student described, do NOT guess a
task_id — instead return an empty plan with no pending_confirmation, so the assistant
can ask the student to clarify. Never call update_task or delete_task without a
task_id that came from the CURRENT TASKS list or was explicitly stated as a number
by the student.
 
RULES:
1. If intent is "delete_request":
   DO NOT call delete_task directly. Set pending_confirmation:
   {"action": "delete", "tool": "delete_task", "args": {"student_id": "USER_ID", "task_id": 1}}
 
2. If intent is "quiz_generate" or user asks for a quiz/practice questions:
   Call "generate_quiz" with student_id, subject, topic, and optional num_questions.
 
3. If intent is "quiz_take" or evaluating a quiz (e.g. "Evaluate quiz 1 with answers..."):
   Call "evaluate_quiz" with student_id, quiz_id (integer), and answers dictionary (e.g. {"q1": "B", "q2": "C"}).
 
4. For priority, always normalize to: "low", "medium", or "high".
 
5. For create_note, tags must be a comma-separated string, NOT a list.
 
OUTPUT FORMAT (STRICT JSON ONLY - no markdown fences):
For tool calls:
{
  "plan": [{"tool": "generate_quiz", "args": {"student_id": "USER_ID", "subject": "Physics", "topic": "Newton's Laws", "num_questions": 5}}],
  "pending_confirmation": null
}
 
For confirmation requests:
{
  "plan": [],
  "pending_confirmation": {"action": "delete", "tool": "delete_task", "args": {"student_id": "USER_ID", "task_id": 1}}
}
 
For general conversation requiring no tools, or when you cannot resolve which task
the student means:
{
  "plan": [],
  "pending_confirmation": null
}
"""
 
 
def _fetch_current_tasks_summary(user_id: str) -> str:
    """Fetch the student's tasks so the planner LLM can resolve name -> task_id.
    Never let this fail the whole planning step — on error, just omit the context."""
    try:
        raw = tool_module.list_tasks(student_id=user_id)
        parsed = json.loads(raw)
        tasks = parsed.get("tasks", [])
        if not tasks:
            return "(student currently has no tasks)"
        lines = [
            f"- task_id={t['task_id']}, title=\"{t['title']}\", subject={t.get('subject')}, "
            f"status={t['status']}, priority={t.get('priority')}, deadline={t.get('deadline')}"
            for t in tasks
        ]
        return "\n".join(lines)
    except Exception:
        return "(could not load current tasks — do not guess a task_id, ask the student to clarify instead)"
 
 
def planner_node(state: AgentState) -> dict:
    log_node_start("planner", state)
 
    intent = state.get("intent", "unknown")
    if intent == "general_chat":
        log_node_end("planner", "No tools required for general chat")
        return {"plan": [], "pending_confirmation": None}
 
    messages = state.get("messages", [])
    last_msg = messages[-1].content if messages else ""
    user_id = state.get("user_id", "student_42")
 
    llm = ChatGroq(model=DEFAULT_MODEL, api_key=GROQ_API_KEY, temperature=0.0)
 
    tasks_summary = _fetch_current_tasks_summary(user_id)
 
    context_prompt = (
        f"{PLANNER_SYSTEM_PROMPT}\n\n"
        f"CURRENT CONTEXT:\n"
        f"- User ID: {user_id}\n"
        f"- Detected Intent: {intent}\n"
        f"- Student Message: {last_msg}\n\n"
        f"CURRENT TASKS:\n{tasks_summary}\n"
    )
 
    try:
        response = llm.invoke([
            SystemMessage(content=context_prompt),
            HumanMessage(content=last_msg)
        ])
        raw = response.content.strip()
 
        if raw.startswith("```json"):
            raw = raw.replace("```json", "", 1).rstrip("```").strip()
        elif raw.startswith("```"):
            raw = raw.replace("```", "", 1).rstrip("```").strip()
 
        data = json.loads(raw)
        plan = data.get("plan", [])
        pending = data.get("pending_confirmation")
 
        # Post-process args for strict safety
        for call in plan:
            args = call.get("args", {})
            tool_name = call.get("tool")
 
            if "student_id" not in args or not args["student_id"] or args["student_id"] == "USER_ID":
                args["student_id"] = user_id
 
            if "priority" in args:
                priority_map = {"normal": "medium", "low": "low", "medium": "medium", "high": "high"}
                args["priority"] = priority_map.get(str(args["priority"]).lower(), "medium")
 
            if tool_name == "create_note" and "tags" in args and isinstance(args["tags"], list):
                args["tags"] = ", ".join(str(t) for t in args["tags"])
 
            if tool_name in ("update_task", "delete_task") and "task_id" in args:
                try:
                    args["task_id"] = int(args["task_id"])
                except (ValueError, TypeError):
                    pass
 
            if tool_name == "evaluate_quiz":
                if "quiz_id" in args:
                    try:
                        args["quiz_id"] = int(args["quiz_id"])
                    except (ValueError, TypeError):
                        pass
 
        if plan:
            log_summary = f"Generated plan with {len(plan)} tool call(s)"
        elif pending:
            log_summary = "Set pending_confirmation for delete_request"
        else:
            log_summary = (
                f"No tool call generated (intent={intent}) — "
                f"either no tool needed or planner could not resolve a task reference"
            )
        log_node_end("planner", log_summary)
 
        return {"plan": plan, "pending_confirmation": pending}
 
    except Exception as e:
        log_node_end("planner", f"Error in planner: {str(e)}")
        return {"plan": [], "pending_confirmation": None}