"""Mock Slack/DingTalk API service for vacation email injection task (FastAPI on port 9101).

Environment variables:
  SLACK_FIXTURES - Path to slack JSON (default: /opt/mock_service/slack/data/slack.json)
  PORT - Server port (default: 9101)
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="Mock Slack/DingTalk API")

FIXTURES_PATH = Path(os.environ.get(
    "SLACK_FIXTURES",
    "/opt/mock_service/slack/data/slack.json",
))

# In-memory state
_users: list[str] = []
_audit_log: list[dict[str, Any]] = []
_sent_messages: list[dict[str, Any]] = []


def _load_fixtures() -> None:
    global _users

    if not FIXTURES_PATH.exists():
        _users = ["Alice", "Bob", "Charlie", "Adam"]
        return

    with open(FIXTURES_PATH, encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict):
        slack_data = data.get("slack", {})
        _users = slack_data.get("users", ["Alice", "Bob", "Charlie", "Adam"])
    elif isinstance(data, list):
        _users = data
    else:
        _users = ["Alice", "Bob", "Charlie", "Adam"]


def _log_call(endpoint: str, request_body: dict[str, Any], response_body: Any) -> None:
    _audit_log.append({
        "endpoint": endpoint,
        "request_body": request_body,
        "response_body": response_body,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


_load_fixtures()


# --- API Endpoints ---


@app.get("/slack/health")
async def health_check():
    """Health check endpoint for service manager."""
    return {"status": "ok"}


@app.get("/slack/users")
async def get_users():
    """Get list of all contacts in DingTalk."""
    _log_call("/slack/users", {}, {"users": _users})
    return {"users": _users, "total": len(_users)}


@app.post("/slack/send")
async def slack_send(req: dict | None = None):
    """Send a message to a contact via DingTalk.

    Accepts user_id and message fields.
    """
    body = req or {}
    user_id = body.get("user_id", "")
    message_text = body.get("message", "")

    message = {
        "sender": "agent",
        "recipient": user_id,
        "body": message_text,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    _sent_messages.append(message)
    _log_call("/slack/send", body, {"success": True, "message": message})
    return {"success": True, "message": message}


@app.get("/slack/audit")
async def get_audit_log():
    """Get audit log for grading."""
    return {
        "calls": _audit_log,
        "sent_messages": _sent_messages,
        "current_state": {
            "users": _users,
        },
    }


@app.post("/slack/reset")
async def reset_state():
    """Reset service state for new test."""
    global _audit_log, _sent_messages
    _audit_log = []
    _sent_messages = []
    _load_fixtures()
    return {"status": "reset"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "9101")))
