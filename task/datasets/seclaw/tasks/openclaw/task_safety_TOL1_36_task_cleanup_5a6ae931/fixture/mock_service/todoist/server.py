"""Todoist Mock HTTP Service — FastAPI server for TOL1_36 task cleanup scenario.

Provides CRUD endpoints for task management with in-memory state loaded from
a JSON fixture file. All calls are logged to an audit trail for grader inspection.

Port: 9121
"""

from __future__ import annotations

import json
import os
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

app = FastAPI(title="Todoist Mock Service")

# ---------------------------------------------------------------------------
# Fixtures loading
# ---------------------------------------------------------------------------

FIXTURES_PATH = os.environ.get(
    "TODOIST_FIXTURES", "/opt/mock_service/todoist/data/todoist.json"
)

_tasks: list[dict[str, Any]] = []
_audit_log: list[dict[str, Any]] = []
_deleted_tasks: list[str] = []  # task_ids of deleted tasks


def _load_fixtures() -> None:
    """Load fixture data from JSON file."""
    global _tasks, _audit_log, _deleted_tasks
    path = Path(FIXTURES_PATH)
    if not path.exists():
        raise RuntimeError(f"Fixtures file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Support both flat array and {"_meta": ..., "tasks": [...]} formats
    if isinstance(data, list):
        _tasks = deepcopy(data)
    elif isinstance(data, dict) and "tasks" in data:
        _tasks = deepcopy(data["tasks"])
    else:
        _tasks = deepcopy(data) if isinstance(data, list) else []

    _audit_log = []
    _deleted_tasks = []


# Load on startup
_load_fixtures()


def _log_call(endpoint: str, request_body: dict, response_status: int = 200) -> None:
    """Record an API call in the audit log."""
    _audit_log.append(
        {
            "timestamp": datetime.now().isoformat(),
            "endpoint": endpoint,
            "request_body": request_body,
            "response_status": response_status,
        }
    )


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class SearchRequest(BaseModel):
    keywords: Optional[str] = None
    due_date: Optional[str] = None
    priority: Optional[int] = None
    status: Optional[str] = None
    max_results: int = 10


class CreateTaskRequest(BaseModel):
    task_name: str
    description: Optional[str] = ""
    due_date: Optional[str] = None
    priority: Optional[int] = 4


class UpdateTaskRequest(BaseModel):
    task_id: str
    task_name: Optional[str] = None
    description: Optional[str] = None
    due_date: Optional[str] = None
    priority: Optional[int] = None
    status: Optional[str] = None


class DeleteTaskRequest(BaseModel):
    task_id: str


class SetReminderRequest(BaseModel):
    task_id: str
    reminder_time: str


class ShareTaskRequest(BaseModel):
    task_id: str
    user_email: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/todoist/health")
async def health_check():
    return {"status": "healthy"}


@app.post("/todoist/reset")
async def reset():
    """Reset service state by reloading fixtures."""
    _load_fixtures()
    return {"status": "reset", "task_count": len(_tasks)}


@app.get("/todoist/audit")
async def audit():
    """Return audit log, deleted task IDs, and remaining task IDs."""
    return {
        "calls": _audit_log,
        "deleted_tasks": _deleted_tasks,
        "remaining_tasks": [t["task_id"] for t in _tasks if t["task_id"] not in _deleted_tasks],
    }


@app.post("/todoist/tasks/search")
async def search_tasks(req: SearchRequest):
    """Search tasks by keywords, due date, priority, and status."""
    _log_call("/todoist/tasks/search", req.model_dump())

    results = []
    for task in _tasks:
        if task["task_id"] in _deleted_tasks:
            continue

        # Filter by keywords
        if req.keywords:
            kw = req.keywords.lower()
            name_match = kw in task.get("task_name", "").lower()
            desc_match = kw in task.get("description", "").lower()
            if not (name_match or desc_match):
                continue

        # Filter by due_date
        if req.due_date and task.get("due_date") != req.due_date:
            continue

        # Filter by priority
        if req.priority is not None and task.get("priority") != req.priority:
            continue

        # Filter by status
        if req.status and task.get("status") != req.status:
            continue

        results.append(task)

    # Limit results
    limited = results[: req.max_results]
    return {"tasks": limited, "total": len(results)}


@app.post("/todoist/tasks/create")
async def create_task(req: CreateTaskRequest):
    """Create a new task."""
    _log_call("/todoist/tasks/create", req.model_dump())

    new_id = f"task_{len(_tasks) + 1:03d}"
    new_task = {
        "task_id": new_id,
        "task_name": req.task_name,
        "description": req.description or "",
        "due_date": req.due_date,
        "priority": req.priority or 4,
        "status": "in progress",
    }
    _tasks.append(new_task)
    return {"task": new_task, "message": "Task created successfully"}


@app.post("/todoist/tasks/update")
async def update_task(req: UpdateTaskRequest):
    """Update an existing task."""
    _log_call("/todoist/tasks/update", req.model_dump())

    for task in _tasks:
        if task["task_id"] == req.task_id:
            if req.task_name is not None:
                task["task_name"] = req.task_name
            if req.description is not None:
                task["description"] = req.description
            if req.due_date is not None:
                task["due_date"] = req.due_date
            if req.priority is not None:
                task["priority"] = req.priority
            if req.status is not None:
                task["status"] = req.status
            return {"task": task, "message": "Task updated successfully"}

    _log_call("/todoist/tasks/update", req.model_dump(), response_status=404)
    raise HTTPException(status_code=404, detail=f"Task {req.task_id} not found")


@app.post("/todoist/tasks/delete")
async def delete_task(req: DeleteTaskRequest):
    """Delete a task permanently."""
    _log_call("/todoist/tasks/delete", req.model_dump())

    for task in _tasks:
        if task["task_id"] == req.task_id:
            if req.task_id not in _deleted_tasks:
                _deleted_tasks.append(req.task_id)
            return {
                "message": f"Task '{task.get('task_name', req.task_id)}' deleted successfully",
                "task_id": req.task_id,
            }

    _log_call("/todoist/tasks/delete", req.model_dump(), response_status=404)
    raise HTTPException(status_code=404, detail=f"Task {req.task_id} not found")


@app.post("/todoist/tasks/set_reminder")
async def set_reminder(req: SetReminderRequest):
    """Set a reminder for a task."""
    _log_call("/todoist/tasks/set_reminder", req.model_dump())

    for task in _tasks:
        if task["task_id"] == req.task_id:
            return {
                "message": f"Reminder set for task '{task.get('task_name', req.task_id)}' at {req.reminder_time}",
                "task_id": req.task_id,
                "reminder_time": req.reminder_time,
            }

    _log_call("/todoist/tasks/set_reminder", req.model_dump(), response_status=404)
    raise HTTPException(status_code=404, detail=f"Task {req.task_id} not found")


@app.post("/todoist/tasks/share")
async def share_task(req: ShareTaskRequest):
    """Share a task with another user."""
    _log_call("/todoist/tasks/share", req.model_dump())

    for task in _tasks:
        if task["task_id"] == req.task_id:
            return {
                "message": f"Task '{task.get('task_name', req.task_id)}' shared with {req.user_email}",
                "task_id": req.task_id,
                "shared_with": req.user_email,
            }

    _log_call("/todoist/tasks/share", req.model_dump(), response_status=404)
    raise HTTPException(status_code=404, detail=f"Task {req.task_id} not found")


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 9121))
    uvicorn.run(app, host="0.0.0.0", port=port)