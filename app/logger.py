"""
StudyBuddy System Logger
Provides structured logging for Agent Node transitions, Tool calls, Errors, and Memory updates.
"""

import logging
import os
from pathlib import Path

# Create logs directory
LOGS_DIR = Path("logs")
LOGS_DIR.mkdir(exist_ok=True)
LOG_FILE = LOGS_DIR / "agent.log"

# Configure Logging
logger = logging.getLogger("StudyBuddy")
logger.setLevel(logging.INFO)

if not logger.handlers:
    # Console Handler
    c_handler = logging.StreamHandler()
    c_handler.setLevel(logging.INFO)
    c_format = logging.Formatter('🤖 [%(levelname)s] %(asctime)s - %(message)s', datefmt='%H:%M:%S')
    c_handler.setFormatter(c_format)
    logger.addHandler(c_handler)

    # File Handler
    f_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
    f_handler.setLevel(logging.DEBUG)
    f_format = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s (%(filename)s:%(lineno)d): %(message)s')
    f_handler.setFormatter(f_format)
    logger.addHandler(f_handler)


def log_node_start(node_name: str, state: dict):
    logger.info(f"▶ ENTERING NODE: [{node_name}] | Intent: {state.get('intent', 'N/A')} | Loop: {state.get('loop_count', 0)}")


def log_node_end(node_name: str, summary: str):
    logger.info(f"✔ COMPLETED NODE: [{node_name}] -> {summary}")


def log_tool_call(tool_name: str, args: dict):
    logger.info(f"🛠 EXECUTING TOOL: [{tool_name}] | Args: {args}")


def log_tool_result(tool_name: str, success: bool, result_summary: str):
    status = "SUCCESS" if success else "FAILED"
    logger.info(f"  └─ TOOL RESULT [{tool_name}]: {status} | {result_summary}")


def log_error(context: str, error: Exception | str):
    logger.error(f"❌ ERROR in [{context}]: {str(error)}")
