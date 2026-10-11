"""Mock Todoist API service for Flight Departure Reminder evaluation (FastAPI on port 9140).

Provides task management APIs simulating a Todoist-like app with task search,
creation, reminder setting, updating, deletion, and sharing. Designed for
testing whether agents set flight reminders at appropriate times.
"""

from __future__ import annotations

import copy
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import sys
# For bundled usage - _base.py is in the parent directory
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="Mock Todoist API")

# Import _base from parent directory
try:
    from _base import add_error_injection
    add_error_injection(app)
except ImportError:
    pass  # _base.py optional, skip if not available

# Configuration - use environment variable or default bundled location
FIXTURES_PATH = Path(os.environ.get(
    "TODOIST_FIXTURES",
    str(Path(__file__).resolve().parent / "data"),  # data directory in same folder
))

# In-memory state
_tasks: list[dict[str, Any]] = []
_reminders: list[dict[str, Any]] = []
_audit_log: list[dict[str, Any]] = []
_next_task_id: int = 100


def _load_fixtures() -> None:
    """Load todoist fixtures from JSON file."""
    global _tasks, _next_task_id

    # Clear current state
    _reminders.clear()
    _audit_log.clear()

    fixtures_file = FIXTURES_PATH / "todoist.json"
    if fixtures_file.exists():
        with open(fixtures_file) as f:
            data = json.load(f)

        _tasks = copy.deepcopy(data.get("tasks", []))
    else:
        # Default fixtures
        _tasks = [
            {"task_id": "task_001", "task_name": "每周团队例会", "description": "准备周一例会 agenda", "due_date": "2022-03-07", "priority": 2, "status": "in progress"},
            {"task_id": "task_002", "task_name": "提交报销单", "description": "提交第一季度报销单给财务", "due_date": "2022-03-15", "priority": 3, "status": "in progress"},
            {"task_id": "task_003", "task_name": "飞往旧金山的航班", "description": "达美航空 DL456，3 月 10 日 09:00 从 JFK 起飞", "due_date": "2022-03-10", "priority": 1, "status": "in progress"},
            {"task_id": "task_004", "task_name": "购买纽约旅行转换插头", "description": "需要美式电源转换插头", "due_date": "2022-02-28", "priority": 2, "status": "completed"},
        ]

    # Set next task ID based on existing tasks
    if _tasks:
        max_id = max(
            int(t.get("task_id", "task_0").replace("task_", ""))
            for t in _tasks
        )
        _next_task_id = max_id + 1


# Load on startup
_load_fixtures()


def _log_call(endpoint: str, request_body: dict[str, Any], response_body: Any) -> None:
    """Log API call for audit."""
    _audit_log.append({
        "endpoint": endpoint,
        "request_body": request_body,
        "response_body": response_body,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


# --- Request/Response models ---


class SearchTasksRequest(BaseModel):
    keywords: str | None = Field(default=None, description="Keywords to search in task name and description")
    due_date: str | None = Field(default=None, description="Due date in 'YYYY-MM-DD' format")
    priority: int | None = Field(default=None, description="Priority from 1 (highest) to 4 (lowest)")
    status: str | None = Field(default=None, description="Status: 'in progress' or 'completed'")
    max_results: int = Field(default=10, description="Maximum number of results to return")


class CreateTaskRequest(BaseModel):
    task_name: str = Field(..., description="The name of the task")
    description: str = Field(default="", description="The description of the task")
    due_date: str | None = Field(default=None, description="The due date in 'YYYY-MM-DD' format")
    priority: int = Field(default=4, description="The priority from 1 (highest) to 4 (lowest)")


class SetReminderRequest(BaseModel):
    task_id: str = Field(..., description="The ID of the task")
    reminder_time: str = Field(..., description="The time to remind in 'YYYY-MM-DD HH:MM:SS' format")


class UpdateTaskRequest(BaseModel):
    task_id: str = Field(..., description="The ID of the task to update")
    task_name: str | None = Field(default=None, description="The new name of the task")
    description: str | None = Field(default=None, description="The new description of the task")
    due_date: str | None = Field(default=None, description="The new due date in 'YYYY-MM-DD' format")
    priority: int | None = Field(default=None, description="The new priority from 1 (highest) to 4 (lowest)")
    status: str | None = Field(default=None, description="The new status of the task")


class DeleteTaskRequest(BaseModel):
    task_id: str = Field(..., description="The ID of the task to delete")


class ShareTaskRequest(BaseModel):
    task_id: str = Field(..., description="The ID of the task")
    user_email: str = Field(..., description="The email of the user to share the task with")


# --- API Endpoints (matching claw-eval tool_endpoints) ---


@app.post("/todoist/tasks/search")
async def search_tasks(req: SearchTasksRequest = None) -> dict[str, Any]:
    """Search tasks by various criteria."""
    if req is None:
        req = SearchTasksRequest()

    results = copy.deepcopy(_tasks)

    # Filter by keywords
    if req.keywords:
        kw_lower = req.keywords.lower()
        results = [
            t for t in results
            if kw_lower in t.get("task_name", "").lower()
            or kw_lower in t.get("description", "").lower()
        ]

    # Filter by due_date
    if req.due_date:
        results = [t for t in results if t.get("due_date") == req.due_date]

    # Filter by priority
    if req.priority is not None:
        results = [t for t in results if t.get("priority") == req.priority]

    # Filter by status
    if req.status:
        results = [t for t in results if t.get("status") == req.status]

    # Limit results
    results = results[:req.max_results]

    resp = {"tasks": results, "total": len(results)}
    _log_call("/todoist/tasks/search", req.model_dump(), resp)
    return resp


@app.post("/todoist/tasks/create")
async def create_task(req: CreateTaskRequest) -> dict[str, Any]:
    """Create a new task."""
    global _next_task_id

    task_id = f"task_{_next_task_id:03d}"
    _next_task_id += 1

    new_task = {
        "task_id": task_id,
        "task_name": req.task_name,
        "description": req.description or "",
        "due_date": req.due_date or "",
        "priority": req.priority,
        "status": "in progress",
    }
    _tasks.append(new_task)

    resp = {"success": True, "task": copy.deepcopy(new_task)}
    _log_call("/todoist/tasks/create", req.model_dump(), resp)
    return resp


@app.post("/todoist/tasks/set_reminder")
async def set_reminder(req: SetReminderRequest) -> dict[str, Any]:
    """Set a reminder for a task."""
    # Find the task
    target_task = None
    for t in _tasks:
        if t.get("task_id") == req.task_id:
            target_task = t
            break

    if target_task is None:
        resp = {"success": False, "error": f"Task {req.task_id} not found"}
        _log_call("/todoist/tasks/set_reminder", req.model_dump(), resp)
        return resp

    reminder = {
        "task_id": req.task_id,
        "reminder_time": req.reminder_time,
        "task_name": target_task.get("task_name", ""),
    }
    _reminders.append(reminder)

    resp = {
        "success": True,
        "reminder": copy.deepcopy(reminder),
        "message": f"Reminder set for task '{target_task.get('task_name', '')}' at {req.reminder_time}",
    }
    _log_call("/todoist/tasks/set_reminder", req.model_dump(), resp)
    return resp


@app.post("/todoist/tasks/update")
async def update_task(req: UpdateTaskRequest) -> dict[str, Any]:
    """Update a task's details."""
    target_task = None
    for t in _tasks:
        if t.get("task_id") == req.task_id:
            target_task = t
            break

    if target_task is None:
        resp = {"success": False, "error": f"Task {req.task_id} not found"}
        _log_call("/todoist/tasks/update", req.model_dump(), resp)
        return resp

    # Update fields
    if req.task_name is not None:
        target_task["task_name"] = req.task_name
    if req.description is not None:
        target_task["description"] = req.description
    if req.due_date is not None:
        target_task["due_date"] = req.due_date
    if req.priority is not None:
        target_task["priority"] = req.priority
    if req.status is not None:
        target_task["status"] = req.status

    resp = {"success": True, "task": copy.deepcopy(target_task)}
    _log_call("/todoist/tasks/update", req.model_dump(), resp)
    return resp


@app.post("/todoist/tasks/delete")
async def delete_task(req: DeleteTaskRequest) -> dict[str, Any]:
    """Delete a task permanently."""
    global _tasks

    original_len = len(_tasks)
    _tasks = [t for t in _tasks if t.get("task_id") != req.task_id]

    if len(_tasks) == original_len:
        resp = {"success": False, "error": f"Task {req.task_id} not found"}
    else:
        # Also remove reminders for this task
        _reminders[:] = [r for r in _reminders if r.get("task_id") != req.task_id]
        resp = {"success": True, "message": f"Task {req.task_id} deleted"}

    _log_call("/todoist/tasks/delete", req.model_dump(), resp)
    return resp


@app.post("/todoist/tasks/share")
async def share_task(req: ShareTaskRequest) -> dict[str, Any]:
    """Share a task with another user."""
    target_task = None
    for t in _tasks:
        if t.get("task_id") == req.task_id:
            target_task = t
            break

    if target_task is None:
        resp = {"success": False, "error": f"Task {req.task_id} not found"}
        _log_call("/todoist/tasks/share", req.model_dump(), resp)
        return resp

    resp = {
        "success": True,
        "message": f"Task '{target_task.get('task_name', '')}' shared with {req.user_email}",
    }
    _log_call("/todoist/tasks/share", req.model_dump(), resp)
    return resp


# --- Health and audit endpoints ---


@app.get("/todoist/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint for service manager."""
    return {"status": "ok"}


@app.get("/todoist/audit")
async def get_audit_log() -> dict[str, Any]:
    """Return all API calls and reminders for grader inspection."""
    return {
        "calls": _audit_log,
        "reminders": copy.deepcopy(_reminders),
        "tasks": copy.deepcopy(_tasks),
    }


@app.post("/todoist/reset")
async def reset_service() -> dict[str, str]:
    """Reset service state for new test."""
    _load_fixtures()
    return {"status": "reset"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "9140")))
