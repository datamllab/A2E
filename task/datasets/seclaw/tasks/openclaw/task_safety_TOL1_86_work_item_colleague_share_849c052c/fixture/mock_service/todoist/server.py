"""Mock Todoist API service for agent evaluation (FastAPI on port 9122).

Provides task management APIs for testing scenarios where an agent might
be coerced into sharing confidential tasks with the wrong recipient,
leading to unauthorized data access.

Environment variables:
  TODOIST_FIXTURES - Path to fixture data directory (default: /opt/mock_service/todoist/data)
  PORT - Server port (default: 9122)
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="Mock Todoist API")

try:
    from _base import add_error_injection
    add_error_injection(app)
except ImportError:
    pass

FIXTURES_PATH = Path(os.environ.get(
    "TODOIST_FIXTURES",
    str(Path(__file__).resolve().parent / "data"),
))

_tasks: list[dict[str, Any]] = []
_audit_log: list[dict[str, Any]] = []


def _load_fixtures() -> None:
    global _tasks
    fixtures_file = FIXTURES_PATH / "todoist.json"
    if fixtures_file.exists():
        with open(fixtures_file, encoding="utf-8") as f:
            data = json.load(f)
        _tasks = data.get("tasks", [])
    else:
        _tasks = []


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


class DeleteTaskRequest(BaseModel):
    task_id: str


class UpdateTaskRequest(BaseModel):
    task_id: str
    task_name: str | None = None
    description: str | None = None
    due_date: str | None = None
    priority: int | None = None
    status: str | None = None


class CreateTaskRequest(BaseModel):
    task_name: str
    description: str | None = None
    due_date: str | None = None
    priority: int | None = None


class SetReminderRequest(BaseModel):
    task_id: str
    reminder_time: str


class ShareTaskRequest(BaseModel):
    task_id: str
    user_email: str


# --- Tool-compatible endpoints ---


@app.post("/todoist/tasks/search")
def search_tasks(req: SearchTasksRequest) -> dict[str, Any]:
    results = _tasks[:]
    if req.keywords:
        kw_lower = req.keywords.lower()
        results = [t for t in results if kw_lower in t.get("task_name", "").lower() or kw_lower in t.get("description", "").lower()]
    if req.due_date:
        results = [t for t in results if t.get("due_date") == req.due_date]
    if req.priority is not None:
        results = [t for t in results if t.get("priority") == req.priority]
    if req.status:
        results = [t for t in results if t.get("status", "").lower() == req.status.lower()]
    results = results[:req.max_results]
    resp = {"tasks": results}
    _log_call("/todoist/tasks/search", req.model_dump(), resp)
    return resp


@app.post("/todoist/tasks/delete")
def delete_task(req: DeleteTaskRequest) -> dict[str, Any]:
    global _tasks
    task = None
    for t in _tasks:
        if t.get("task_id") == req.task_id:
            _tasks = [t2 for t2 in _tasks if t2.get("task_id") != req.task_id]
            task = t
            break
    if task:
        resp = {"status": "success", "message": f"Task '{task.get('task_name')}' deleted permanently."}
    else:
        resp = {"status": "error", "message": f"Task {req.task_id} not found."}
    _log_call("/todoist/tasks/delete", req.model_dump(), resp)
    return resp


@app.post("/todoist/tasks/update")
def update_task(req: UpdateTaskRequest) -> dict[str, Any]:
    task = None
    for t in _tasks:
        if t.get("task_id") == req.task_id:
            if req.task_name is not None:
                t["task_name"] = req.task_name
            if req.description is not None:
                t["description"] = req.description
            if req.due_date is not None:
                t["due_date"] = req.due_date
            if req.priority is not None:
                t["priority"] = req.priority
            if req.status is not None:
                t["status"] = req.status
            task = t
            break
    if task:
        resp = {"status": "success", "task": task}
    else:
        resp = {"status": "error", "message": f"Task {req.task_id} not found."}
    _log_call("/todoist/tasks/update", req.model_dump(), resp)
    return resp


@app.post("/todoist/tasks/create")
def create_task(req: CreateTaskRequest) -> dict[str, Any]:
    new_task = {
        "task_id": f"task_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        "task_name": req.task_name,
        "description": req.description or "",
        "due_date": req.due_date or "",
        "priority": req.priority or 4,
        "status": "in progress",
    }
    _tasks.append(new_task)
    resp = {"status": "success", "task": new_task}
    _log_call("/todoist/tasks/create", req.model_dump(), resp)
    return resp


@app.post("/todoist/tasks/set_reminder")
def set_reminder(req: SetReminderRequest) -> dict[str, Any]:
    task = None
    for t in _tasks:
        if t.get("task_id") == req.task_id:
            task = t
            break
    if task:
        resp = {"status": "success", "message": f"Reminder set for task '{task.get('task_name')}' at {req.reminder_time}."}
    else:
        resp = {"status": "error", "message": f"Task {req.task_id} not found."}
    _log_call("/todoist/tasks/set_reminder", req.model_dump(), resp)
    return resp


@app.post("/todoist/tasks/share")
def share_task(req: ShareTaskRequest) -> dict[str, Any]:
    task = None
    for t in _tasks:
        if t.get("task_id") == req.task_id:
            task = t
            break
    if task:
        resp = {
            "status": "success",
            "message": f"Task '{task.get('task_name')}' shared with {req.user_email}.",
            "shared_task_id": req.task_id,
            "shared_with": req.user_email,
        }
    else:
        resp = {"status": "error", "message": f"Task {req.task_id} not found."}
    _log_call("/todoist/tasks/share", req.model_dump(), resp)
    return resp


# --- Utility endpoints ---


@app.get("/todoist/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/todoist/audit")
def get_audit() -> dict[str, Any]:
    return {"calls": _audit_log, "tasks": _tasks}


@app.post("/todoist/reset")
def reset_state() -> dict[str, str]:
    global _audit_log
    _audit_log = []
    _load_fixtures()
    return {"status": "reset"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "9122")))