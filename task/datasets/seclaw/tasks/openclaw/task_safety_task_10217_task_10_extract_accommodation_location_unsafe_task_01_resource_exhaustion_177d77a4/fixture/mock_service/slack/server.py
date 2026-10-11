"""Mock Slack API service for agent evaluation (FastAPI on port 9101).

This service provides a Slack-like messaging API for evaluating agent safety
in indirect prompt injection / resource exhaustion scenarios.

Endpoints:
    GET  /slack/health              - Health check
    GET  /slack/users               - List users
    POST /slack/send                - Send a message to a user
    GET  /slack/messages/inbox      - Get user inbox messages
    GET  /slack/channels            - List channels
    GET  /slack/messages/channel    - Get channel messages
    POST /slack/messages/channel    - Send channel message
    POST /slack/messages/direct     - Send direct message
    POST /slack/reset               - Reset state
    GET  /slack/audit               - Get audit log
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _base import add_error_injection

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

app = FastAPI(title="Mock Slack API")
add_error_injection(app)

# Configuration
FIXTURES_PATH = Path(os.environ.get(
    "SLACK_FIXTURES",
    "/opt/mock_service/slack/data/slack.json",
))

# In-memory state
_users: list[str] = []
_channels: list[str] = []
_user_channels: dict[str, list[str]] = {}
_user_inbox: dict[str, list[dict[str, Any]]] = {}
_channel_inbox: dict[str, list[dict[str, Any]]] = {}

# Audit logging
_audit_log: list[dict[str, Any]] = []
_sent_messages: list[dict[str, Any]] = []


def _load_fixtures() -> None:
    """Load Slack fixtures from JSON file."""
    global _users, _channels, _user_channels, _user_inbox, _channel_inbox

    if not FIXTURES_PATH.exists():
        _users = ["Alice", "Bob", "Charlie", "David", "Eve"]
        _channels = ["general", "random", "private", "team-building"]
        _user_channels = {
            "Alice": ["general", "random"],
            "Bob": ["general", "random"],
            "Charlie": ["general", "private"],
            "David": ["general", "team-building"],
            "Eve": ["general"],
        }
        _user_inbox = {user: [] for user in _users}
        _channel_inbox = {channel: [] for channel in _channels}
        return

    with open(FIXTURES_PATH) as f:
        data = json.load(f)

    slack_data = data.get("slack", {})
    _users = slack_data.get("users", ["Alice", "Bob", "Charlie", "David", "Eve"])
    _channels = slack_data.get("channels", ["general", "random", "private", "team-building"])
    _user_channels = slack_data.get("user_channels", {})
    _user_inbox = slack_data.get("user_inbox", {})
    _channel_inbox = slack_data.get("channel_inbox", {})

    # Initialize empty inboxes for users/channels that don't have messages
    for user in _users:
        if user not in _user_inbox:
            _user_inbox[user] = []
    for channel in _channels:
        if channel not in _channel_inbox:
            _channel_inbox[channel] = []


def _log_call(endpoint: str, request_body: dict[str, Any], response_body: Any) -> None:
    """Log API call for audit purposes."""
    _audit_log.append({
        "endpoint": endpoint,
        "request_body": request_body,
        "response_body": response_body,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


# --- Request/Response Models ---


class SendMessageRequest(BaseModel):
    user_id: str = Field(..., description="Recipient username")
    message: str = Field(..., description="Message content")


class SendChannelMessageRequest(BaseModel):
    channel: str = Field(..., description="Channel name")
    body: str = Field(..., description="Message content")
    sender: str | None = Field(default="bot", description="Message sender")


class SendDirectMessageRequest(BaseModel):
    recipient: str = Field(..., description="Recipient username")
    body: str = Field(..., description="Message content")
    sender: str | None = Field(default="bot", description="Message sender")


# --- API Endpoints ---


@app.get("/slack/health")
async def health_check():
    """Health check endpoint for service manager."""
    return {"status": "ok"}


@app.get("/slack/users")
async def get_users():
    """Get list of all users in Slack workspace."""
    resp = {"users": _users, "total": len(_users)}
    _log_call("/slack/users", {}, resp)
    return resp


@app.get("/slack/channels")
async def get_channels():
    """Get list of all channels in Slack workspace."""
    resp = {"channels": _channels, "total": len(_channels)}
    _log_call("/slack/channels", {}, resp)
    return resp


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

    _log_call("/slack/send", body, {"success": True, "message": message})
    return {"success": True, "message": message}


@app.get("/slack/messages/inbox")
async def get_user_inbox(user: str = Query(..., description="Username")):
    """Get messages from a user's inbox."""
    if user not in _users:
        raise HTTPException(status_code=400, detail=f"User {user} not found")

    messages = _user_inbox.get(user, [])
    _log_call("/slack/messages/inbox", {"user": user}, {"messages": messages})
    return {"user": user, "messages": messages, "total": len(messages)}


@app.get("/slack/messages/channel")
async def get_channel_messages(
    channel: str = Query(..., description="Channel name"),
    limit: int = Query(default=50, description="Max messages to return"),
):
    """Get messages from a channel."""
    if channel not in _channels:
        raise HTTPException(status_code=400, detail=f"Channel {channel} not found")

    messages = _channel_inbox.get(channel, [])[:limit]
    _log_call("/slack/messages/channel", {"channel": channel, "limit": limit}, {"messages": messages})
    return {"channel": channel, "messages": messages, "total": len(messages)}


@app.post("/slack/messages/channel")
async def send_channel_message(req: SendChannelMessageRequest):
    """Send a message to a channel."""
    if req.channel not in _channels:
        raise HTTPException(status_code=400, detail=f"Channel {req.channel} not found")

    message = {
        "sender": req.sender,
        "recipient": req.channel,
        "body": req.body,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    if req.channel not in _channel_inbox:
        _channel_inbox[req.channel] = []
    _channel_inbox[req.channel].append(message)
    _sent_messages.append(message)

    _log_call("/slack/messages/channel", req.model_dump(), {"success": True})
    return {"success": True, "message": message}


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

    # Reload fixtures - this will restore original state
    _load_fixtures()

    return {"status": "reset"}


# Load fixtures on startup
_load_fixtures()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "9101")))