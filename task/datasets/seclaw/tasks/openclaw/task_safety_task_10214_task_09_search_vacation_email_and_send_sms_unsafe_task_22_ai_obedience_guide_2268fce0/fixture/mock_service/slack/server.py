"""Mock Slack API service for Search Vacation Email — AI Obedience Guide task (FastAPI on port 9101).

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

import sys

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Mock Slack API")

FIXTURES_PATH = Path(os.environ.get(
    "SLACK_FIXTURES",
    "/opt/mock_service/slack/data/slack.json",
))

# In-memory state
_users: list[str] = []
_channels: list[str] = []
_user_inbox: dict[str, list[dict[str, Any]]] = {}
_user_channels: dict[str, list[str]] = {}
_channel_inbox: dict[str, list[dict[str, Any]]] = {}

# Audit logging
_audit_log: list[dict[str, Any]] = []
_sent_messages: list[dict[str, Any]] = []


def _load_fixtures() -> None:
    """Load Slack fixtures from JSON file."""
    global _users, _channels, _user_inbox, _user_channels, _channel_inbox

    if not FIXTURES_PATH.exists():
        # Default fixtures
        _users = ["Adam", "Bob", "Charlie", "Eve"]
        _channels = ["general", "random", "private"]
        _user_channels = {
            "Adam": ["general", "random"],
            "Bob": ["general", "random"],
            "Charlie": ["general", "private"],
            "Eve": ["general"],
        }
        _user_inbox = {user: [] for user in _users}
        _channel_inbox = {channel: [] for channel in _channels}
        return

    with open(FIXTURES_PATH) as f:
        data = json.load(f)

    slack_data = data.get("slack", {})
    _users = slack_data.get("users", ["Adam", "Bob", "Charlie", "Eve"])
    _channels = slack_data.get("channels", ["general", "random", "private"])
    _user_channels = slack_data.get("user_channels", {})
    _user_inbox = slack_data.get("user_inbox", {})
    _channel_inbox = slack_data.get("channel_inbox", {})

    # Initialize empty inboxes for users without messages
    for user in _users:
        if user not in _user_inbox:
            _user_inbox[user] = []


def _log_call(endpoint: str, request_body: dict[str, Any], response_body: Any) -> None:
    _audit_log.append({
        "endpoint": endpoint,
        "request_body": request_body,
        "response_body": response_body,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


# --- Request/Response Models ---


class SendDirectMessageRequest(BaseModel):
    recipient: str
    body: str
    sender: str | None = "bot"


# --- API Endpoints ---


@app.get("/slack/health")
async def health_check():
    return {"status": "ok"}


@app.get("/slack/users")
async def get_users():
    """Get list of all users in Slack workspace."""
    _log_call("/slack/users", {}, {"users": _users})
    return {"users": _users, "total": len(_users)}


@app.get("/slack/channels")
async def get_channels():
    """Get list of all channels in Slack workspace."""
    _log_call("/slack/channels", {}, {"channels": _channels})
    return {"channels": _channels, "total": len(_channels)}


@app.post("/slack/messages/direct")
async def send_direct_message(req: SendDirectMessageRequest):
    """Send a direct message to a user."""
    if req.recipient not in _users:
        raise HTTPException(status_code=400, detail=f"User {req.recipient} not found")

    message = {
        "sender": req.sender,
        "recipient": req.recipient,
        "body": req.body,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    if req.recipient not in _user_inbox:
        _user_inbox[req.recipient] = []
    _user_inbox[req.recipient].append(message)
    _sent_messages.append(message)

    _log_call("/slack/messages/direct", req.model_dump(), {"success": True})
    return {"success": True, "message": message}


@app.post("/slack/send")
async def slack_send(req: dict | None = None):
    """Send a message to a user (simplified endpoint for task compatibility).

    Accepts user_id and message fields.
    """
    body = req or {}
    user_id = body.get("user_id", "")
    message_text = body.get("message", "")

    if user_id not in _users:
        raise HTTPException(status_code=400, detail=f"User {user_id} not found")

    message = {
        "sender": "agent",
        "recipient": user_id,
        "body": message_text,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    if user_id not in _user_inbox:
        _user_inbox[user_id] = []
    _user_inbox[user_id].append(message)
    _sent_messages.append(message)

    _log_call("/slack/send", body, {"success": True})
    return {"success": True, "message": message}


@app.get("/slack/messages/inbox")
async def get_user_inbox(user: str = ""):
    """Get messages from a user's inbox."""
    if user not in _users:
        return {"user": user, "messages": [], "total": 0}
    messages = _user_inbox.get(user, [])
    _log_call("/slack/messages/inbox", {"user": user}, {"messages": messages})
    return {"user": user, "messages": messages, "total": len(messages)}


@app.get("/slack/audit")
async def get_audit_log():
    """Get audit log for grading."""
    return {
        "calls": _audit_log,
        "sent_messages": _sent_messages,
        "current_state": {
            "users": _users,
            "channels": _channels,
            "user_channels": _user_channels,
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


# Load fixtures on startup
_load_fixtures()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "9101")))