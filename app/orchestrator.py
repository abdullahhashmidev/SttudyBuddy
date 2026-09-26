"""
StudyBuddy Orchestrator
Wires router -> planner -> tool_executor/confirmation_handler ->
error_handler/evaluator -> response_synthesizer into a LangGraph StateGraph.
"""

from app import quiz_tools


import json
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage

from app.memory import AgentState, get_sqlite_checkpointer
from app.nlu import classify_intent_dict
from app.planner_agent import planner_node
from app.tutor_agent import response_synthesizer_node
from app.logger import logger, log_node_start, log_node_end, log_tool_call, log_tool_result
from app import tools as tool_module

MAX_TOOL_CALLS = 7
MAX_LOOPS = 4

TOOL_REGISTRY = {
    "create_task": tool_module.create_task,
    "list_tasks": tool_module.list_tasks,
    "update_task": tool_module.update_task,
    "delete_task": tool_module.delete_task,
    "create_study_session": tool_module.create_study_session,
    "create_note": tool_module.create_note,
    "search_notes": tool_module.search_notes,
    "generate_quiz": quiz_tools.generate_quiz,
    "evaluate_quiz": quiz_tools.evaluate_quiz,
}


def router_node(state: AgentState) -> dict:
    log_node_start("router", state)
    last_user_msg = ""
    for msg in reversed(state.get("messages", [])):
        if isinstance(msg, HumanMessage):
            last_user_msg = msg.content
            break

    result = classify_intent_dict(last_user_msg, state.get("current_timestamp"))
    intent = result.get("intent", "unknown")
    log_node_end("router", f"Classified intent = {intent}")
    return {"intent": intent}


def tool_executor_node(state: AgentState) -> dict:
    log_node_start("tool_executor", state)
    plan = state.get("plan", [])
    tool_calls_made = state.get("tool_calls_made", 0)

    tool_results, actions_taken, data_modified = [], [], []
    error_state = None
    new_calls = 0

    for call in plan:
        # Remove MAX_TOOL_CALLS limit (or increase significantly)
        # if tool_calls_made + new_calls >= MAX_TOOL_CALLS:
        #     break

        tool_name = call.get("tool")
        args = call.get("args", {})
        fn = TOOL_REGISTRY.get(tool_name)

        if fn is None:
            error_state = {"tool": tool_name, "error": "Unknown tool", "retry_count": 0}
            log_tool_call(tool_name, {"error": "Tool not found in registry"})
            break

        log_tool_call(tool_name, args)
        try:
            raw_result = fn(**args)
            parsed = json.loads(raw_result)
            new_calls += 1

            if parsed.get("status") == "error":
                error_state = {"tool": tool_name, "error": parsed.get("message", "Unknown error"), "retry_count": 0}
                log_tool_result(tool_name, False, parsed.get("message", ""))
                break

            log_tool_result(tool_name, True, parsed.get("message", "OK"))
            tool_results.append({"tool": tool_name, "result": parsed, "status": "success"})
            actions_taken.append({"tool": tool_name, "result": "success", "details": parsed})

            if tool_name in ("create_task", "update_task", "delete_task"):
                data_modified.append({"table": "tasks", "operation": "WRITE", "count": 1})
            elif tool_name == "create_study_session":
                data_modified.append({"table": "study_sessions", "operation": "INSERT", "count": 1})
            elif tool_name == "create_note":
                data_modified.append({"table": "notes", "operation": "INSERT", "count": 1})

        except Exception as e:
            error_state = {"tool": tool_name, "error": str(e), "retry_count": 0}
            log_tool_result(tool_name, False, str(e))
            break

    log_node_end("tool_executor", f"Executed {new_calls} tool call(s)")
    return {
        "tool_results": tool_results,
        "actions_taken": actions_taken,
        "data_modified": data_modified,
        "tool_calls_made": tool_calls_made + new_calls,
        "error_state": error_state,
    }


def error_handler_node(state: AgentState) -> dict:
    log_node_start("error_handler", state)
    error_state = state.get("error_state") or {}
    retry_count = error_state.get("retry_count", 0)

    if retry_count < 2:
        error_state["retry_count"] = retry_count + 1
        log_node_end("error_handler", f"Retrying tool '{error_state.get('tool')}' (attempt {retry_count + 1})")
        return {"error_state": error_state, "is_complete": False}

    log_node_end("error_handler", f"Aborting after retries for tool '{error_state.get('tool')}'")
    return {"error_state": None, "is_complete": True}


def confirmation_handler_node(state: AgentState) -> dict:
    log_node_start("confirmation_handler", state)
    
    # Get the last user message
    last_user_msg = ""
    for msg in reversed(state.get("messages", [])):
        if isinstance(msg, HumanMessage):
            last_user_msg = msg.content.strip().lower()
            break
    
    pending = state.get("pending_confirmation")
    if not pending:
        log_node_end("confirmation_handler", "No pending confirmation")
        return {"is_complete": True}
    
    # Check if user confirmed
    if last_user_msg in ("yes", "y", "confirm", "go ahead", "do it", "sure", "ok", "okay"):
        log_node_end("confirmation_handler", "User confirmed — executing deletion")
        # Convert pending_confirmation to plan
        tool_call = {
            "tool": pending.get("tool"),
            "args": pending.get("args", {})
        }
        return {
            "pending_confirmation": None,
            "plan": [tool_call],
            "is_complete": False
        }
    
    # User rejected
    if last_user_msg in ("no", "n", "cancel", "stop", "never mind", "nope"):
        log_node_end("confirmation_handler", "User rejected deletion")
        return {
            "pending_confirmation": None,
            "plan": [],
            "is_complete": True
        }
    
    # Still waiting for yes/no
    log_node_end("confirmation_handler", "Still awaiting user confirmation (yes/no)")
    return {"is_complete": True}  # Don't loop — wait for next user input

    if last_user_msg in ("yes", "y", "confirm", "go ahead", "do it", "sure"):
        log_node_end("confirmation_handler", "User confirmed")
        return {"pending_confirmation": None, "is_complete": False}

    if last_user_msg in ("no", "n", "cancel", "stop", "never mind"):
        log_node_end("confirmation_handler", "User rejected")
        return {"pending_confirmation": None, "plan": [], "is_complete": True}

    log_node_end("confirmation_handler", "Awaiting confirmation")
    return {"is_complete": True}


def evaluator_node(state: AgentState) -> dict:
    log_node_start("evaluator", state)
    loop_count = state.get("loop_count", 0) + 1
    is_complete = True
    log_node_end("evaluator", f"is_complete={is_complete} | loop={loop_count}")
    return {"is_complete": is_complete, "loop_count": loop_count}


def route_after_router(state: AgentState) -> str:
    return "response_synthesizer" if state.get("intent") == "general_chat" else "planner"


def route_after_planner(state: AgentState) -> str:
    if state.get("pending_confirmation") is not None:
        return "confirmation_handler"
    if state.get("plan"):
        return "tool_executor"
    return "response_synthesizer"


def route_after_confirmation(state: AgentState) -> str:
    return "tool_executor" if state.get("plan") else "response_synthesizer"


def route_after_tool_executor(state: AgentState) -> str:
    return "error_handler" if state.get("error_state") is not None else "evaluator"


def route_after_evaluator(state: AgentState) -> str:
    return "response_synthesizer" if state.get("is_complete") else "planner"


def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("router", router_node)
    graph.add_node("planner", planner_node)
    graph.add_node("confirmation_handler", confirmation_handler_node)
    graph.add_node("tool_executor", tool_executor_node)
    graph.add_node("error_handler", error_handler_node)
    graph.add_node("evaluator", evaluator_node)
    graph.add_node("response_synthesizer", response_synthesizer_node)

    graph.set_entry_point("router")

    graph.add_conditional_edges("router", route_after_router,
        {"planner": "planner", "response_synthesizer": "response_synthesizer"})

    graph.add_conditional_edges("planner", route_after_planner,
        {"confirmation_handler": "confirmation_handler", "tool_executor": "tool_executor",
         "response_synthesizer": "response_synthesizer"})

    graph.add_conditional_edges("confirmation_handler", route_after_confirmation,
        {"tool_executor": "tool_executor", "response_synthesizer": "response_synthesizer"})

    graph.add_conditional_edges("tool_executor", route_after_tool_executor,
        {"error_handler": "error_handler", "evaluator": "evaluator"})

    graph.add_edge("error_handler", "evaluator")

    graph.add_conditional_edges("evaluator", route_after_evaluator,
        {"planner": "planner", "response_synthesizer": "response_synthesizer"})

    graph.add_edge("response_synthesizer", END)

    checkpointer = get_sqlite_checkpointer()
    return graph.compile(checkpointer=checkpointer)