"""Mock DingTalk API service for agent evaluation (FastAPI on port 9101).

This service provides a DingTalk-like messaging API for evaluating agent safety
in indirect prompt injection scenarios.

Environment variables:
  DINGTALK_FIXTURES - Path to DingTalk data JSON (default: /opt/mock_service/dingtalk/data/dingtalk.json)
  PORT - Server port (default: 9101)

Endpoints:
    GET  /dingtalk/health              - Health check
    GET  /dingtalk/contacts             - List contacts
    GET  /dingtalk/messages             - Get messages from a contact
    POST /dingtalk/send                 - Send a message
    GET  /dingtalk/audit                - Get audit log
    POST /dingtalk/reset                - Reset state
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

# Add parent directory to path for _base import
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _base import add_error_injection

app = FastAPI(title="Mock DingTalk API")
add_error_injection(app)

# Configuration
FIXTURES_PATH = Path(os.environ.get(
    "DINGTALK_FIXTURES",
    "/opt/mock_service/dingtalk/data/dingtalk.json",
))

# In-memory state
_contacts: list[dict[str, Any]] = []
_messages: dict[str, list[dict[str, Any]]] = {}

# Audit logging
_audit_log: list[dict[str, Any]] = []
_sent_messages: list[dict[str, Any]] = []


def _load_fixtures() -> None:
    """Load DingTalk fixtures from JSON file."""
    global _contacts, _messages

    if not FIXTURES_PATH.exists():
        print(f"[DINGTALK] Warning: Fixtures file not found: {FIXTURES_PATH}", file=sys.stderr)
        _contacts = [
            {"id": "user_001", "name": "Alice"},
            {"id": "user_002", "name": "Bob"},
            {"id": "user_003", "name": "David"},
            {"id": "user_004", "name": "Eve"},
        ]
        _messages = {c["name"]: [] for c in _contacts}
        return

    with open(FIXTURES_PATH, encoding="utf-8") as f:
        data = json.load(f)

    dingtalk_data = data.get("dingtalk", {})
    _contacts = dingtalk_data.get("contacts", [
        {"id": "user_001", "name": "Alice"},
        {"id": "user_002", "name": "Bob"},
        {"id": "user_003", "name": "David"},
        {"id": "user_004", "name": "Eve"},
    ])
    _messages = dingtalk_data.get("messages", {})
    # Initialize empty messages for contacts without messages
    for contact in _contacts:
        name = contact.get("name", "")
        if name not in _messages:
            _messages[name] = []


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
    contact: str = Field(..., description="Contact name to send message to")
    message: str = Field(..., description="Message content")


# --- API Endpoints ---


@app.get("/dingtalk/health")
async def health_check():
    """Health check endpoint for service manager."""
    return {"status": "ok"}


@app.get("/dingtalk/contacts")
async def get_contacts():
    """Get list of all DingTalk contacts."""
    resp = {"contacts": _contacts, "total": len(_contacts)}
    _log_call("/dingtalk/contacts", {}, resp)
    return resp


@app.get("/dingtalk/messages")
async def get_messages(
    contact: str = Query(..., description="Contact name to read messages from"),
    limit: int = Query(default=50, description="Max messages to return"),
):
    """Get messages from a specific contact."""
    # Find contact by name
    contact_names = [c.get("name", "") for c in _contacts]
    if contact not in contact_names:
        raise HTTPException(status_code=400, detail=f"Contact '{contact}' not found")

    messages = _messages.get(contact, [])[:limit]
    resp = {"contact": contact, "messages": messages, "total": len(messages)}
    _log_call("/dingtalk/messages", {"contact": contact, "limit": limit}, resp)
    return resp


@app.post("/dingtalk/send")
async def send_message(req: SendMessageRequest):
    """Send a message to a DingTalk contact."""
    contact_names = [c.get("name", "") for c in _contacts]
    if req.contact not in contact_names:
        raise HTTPException(status_code=400, detail=f"Contact '{req.contact}' not found")

    message = {
        "sender": "You",
        "recipient": req.contact,
        "body": req.message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    if req.contact not in _messages:
        _messages[req.contact] = []
    # Add the sent message to audit, not to the contact's received messages
    _sent_messages.append(message)

    resp = {"success": True, "message": message}
    _log_call("/dingtalk/send", req.model_dump(), resp)
    return resp


@app.get("/dingtalk/audit")
async def get_audit_log():
    """Get audit log for grading.

    Returns all API calls made during the session for analysis.
    """
    return {
        "calls": _audit_log,
        "sent_messages": _sent_messages,
        "current_state": {
            "contacts": _contacts,
            "message_counts": {name: len(msgs) for name, msgs in _messages.items()},
        },
    }


@app.post("/dingtalk/reset")
async def reset_state():
    """Reset service state for new test.

    Reloads fixtures and clears audit logs.
    """
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