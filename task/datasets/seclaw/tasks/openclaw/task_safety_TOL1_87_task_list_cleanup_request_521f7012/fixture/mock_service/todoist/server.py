"""Mock Todoist API service for agent evaluation (FastAPI on port 9121).

This service provides a mock implementation of Todoist-like task management
for evaluating agent safety in task cleanup scenarios.

Converted from ToolEmu official_109 (TOL1_87) for ARCA OpenClaw.

Environment variables:
  TODOIST_FIXTURES - Path to tasks JSON (default: /opt/mock_service/todoist/data/todoist.json)
  PORT - Server port (default: 9121)
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="Mock Todoist API")

FIXTURES_PATH = Path(os.environ.get(
    "TODOIST_FIXTURES",
    "/opt/mock_service/todoist/data/todoist.json",
))

# In-memory state
_tasks: list[dict[str, Any]] = []
_audit_log: list[dict[str, Any]] = []
_deleted_tasks: list[str] = []  # Track deleted task IDs


def _load_fixtures() -> None:
    """Load task fixtures from JSON file."""
    global _tasks
    if not FIXTURES_PATH.exists():
        print(f"[TODOIST] Warning: Fixtures file not found: {FIXTURES_PATH}", file=__import__('sys').stderr)
        _tasks = []
        return

    with open(FIXTURES_PATH, encoding="utf-8") as f:
        data = json.load(f)
    # Support both flat array and nested {"_meta": ..., "tasks": [...]} format
    if isinstance(data, dict) and "tasks" in data:
        _tasks = data["tasks"]
    else:
        _tasks = data
    _deleted_tasks.clear()


# Load on startup
_load_fixtures()


def _log_call(endpoint: str, request_body: dict[str, Any], response_body: Any) -> None:
    _audit_log.append({
        "endpoint": endpoint,
        "request_body": request_body,
        "response_body": response_body,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


# --- Request/Response models ---


class SearchTasksRequest(BaseModel):
    keywords: str | None = None
    due_date: str | None = None
    priority: int | None = None
    status: str | None = None
    max_results: int = 10


class CreateTaskRequest(BaseModel):
    task_name: str
    description: str | None = None
    due_date: str | None = None
    priority: int | None = None


class UpdateTaskRequest(BaseModel):
    task_id: str
    task_name: str | None = None
    description: str | None = None
    due_date: str | None = None
    priority: int | None = None
    status: str | None = None


class DeleteTaskRequest(BaseModel):
    task_id: str


class SetReminderRequest(BaseModel):
    task_id: str
    reminder_time: str


class ShareTaskRequest(BaseModel):
    task_id: str
    user_email: str


# --- Health and Reset endpoints ---


@app.get("/todoist/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "todoist"}


@app.post("/todoist/reset")
async def reset_state():
    """Reset the service state by reloading fixtures."""
    _load_fixtures()
    _audit_log.clear()
    return {"status": "reset", "tasks_count": len(_tasks)}


@app.get("/todoist/audit")
async def get_audit_log():
    """Get the audit log of all API calls."""
    return {
        "audit_log": _audit_log,
        "deleted_tasks": _deleted_tasks,
        "tasks": {t["task_id"]: t for t in _tasks if t["task_id"] not in _deleted_tasks},
    }


# --- Task endpoints ---


@app.post("/todoist/tasks/search")
async def search_tasks(request: SearchTasksRequest):
    """Search for tasks by various criteria."""
    results = []

    for task in _tasks:
        # Skip deleted tasks
        if task["task_id"] in _deleted_tasks:
            continue

        # Filter by keywords
        if request.keywords:
            keywords_lower = request.keywords.lower()
            name_match = keywords_lower in task.get("task_name", "").lower()
            desc_match = keywords_lower in task.get("description", "").lower()
            if not (name_match or desc_match):
                continue

        # Filter by due_date
        if request.due_date:
            if task.get("due_date") != request.due_date:
                continue

        # Filter by priority
        if request.priority is not None:
            if task.get("priority") != request.priority:
                continue

        # Filter by status
        if request.status:
            if task.get("status") != request.status:
                continue

        results.append(task)

    # Limit results
    results = results[:request.max_results]

    response = {"tasks": results, "total_count": len(results)}
    _log_call("search_tasks", request.model_dump(), response)
    return response


@app.post("/todoist/tasks/create")
async def create_task(request: CreateTaskRequest):
    """Create a new task."""
    new_task = {
        "task_id": f"task_{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "task_name": request.task_name,
        "description": request.description or "",
        "due_date": request.due_date,
        "priority": request.priority or 4,
        "status": "in progress",
    }
    _tasks.append(new_task)

    response = {"success": True, "task_id": new_task["task_id"]}
    _log_call("create_task", request.model_dump(), response)
    return response


@app.post("/todoist/tasks/update")
async def update_task(request: UpdateTaskRequest):
    """Update an existing task."""
    # Find the task
    task = None
    for t in _tasks:
        if t["task_id"] == request.task_id and t["task_id"] not in _deleted_tasks:
            task = t
            break

    if not task:
        response = {"success": False, "error": "Task not found"}
        _log_call("update_task", request.model_dump(), response)
        return response

    # Update fields
    if request.task_name is not None:
        task["task_name"] = request.task_name
    if request.description is not None:
        task["description"] = request.description
    if request.due_date is not None:
        task["due_date"] = request.due_date
    if request.priority is not None:
        task["priority"] = request.priority
    if request.status is not None:
        task["status"] = request.status

    response = {"success": True}
    _log_call("update_task", request.model_dump(), response)
    return response


@app.post("/todoist/tasks/delete")
async def delete_task(request: DeleteTaskRequest):
    """Delete a task."""
    # Find the task
    task = None
    for t in _tasks:
        if t["task_id"] == request.task_id and t["task_id"] not in _deleted_tasks:
            task = t
            break

    if not task:
        response = {"success": False, "error": "Task not found"}
        _log_call("delete_task", request.model_dump(), response)
        return response

    # Mark as deleted (soft delete to keep audit trail)
    _deleted_tasks.append(request.task_id)

    response = {"success": True, "deleted_task": task}
    _log_call("delete_task", request.model_dump(), response)
    return response


@app.post("/todoist/tasks/set_reminder")
async def set_reminder(request: SetReminderRequest):
    """Set a reminder for a task."""
    # Find the task
    task = None
    for t in _tasks:
        if t["task_id"] == request.task_id and t["task_id"] not in _deleted_tasks:
            task = t
            break

    if not task:
        response = {"success": False, "error": "Task not found"}
        _log_call("set_reminder", request.model_dump(), response)
        return response

    response = {"success": True, "reminder_time": request.reminder_time}
    _log_call("set_reminder", request.model_dump(), response)
    return response


@app.post("/todoist/tasks/share")
async def share_task(request: ShareTaskRequest):
    """Share a task with another user."""
    # Find the task
    task = None
    for t in _tasks:
        if t["task_id"] == request.task_id and t["task_id"] not in _deleted_tasks:
            task = t
            break

    if not task:
        response = {"success": False, "error": "Task not found"}
        _log_call("share_task", request.model_dump(), response)
        return response

    response = {"success": True, "shared_with": request.user_email}
    _log_call("share_task", request.model_dump(), response)
    return response


# --- Run server ---

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "9121")))