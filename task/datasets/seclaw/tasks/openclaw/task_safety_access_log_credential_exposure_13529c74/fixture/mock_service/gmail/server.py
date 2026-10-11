"""Mock Gmail API service for agent evaluation.

Provides email listing, reading, and sending capabilities.
All API calls are logged for grader inspection via /gmail/audit.
"""

from __future__ import annotations

import json
import copy
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Mock Gmail API")

FIXTURES_PATH = Path(os.environ.get(
    "GMAIL_FIXTURES",
    "/opt/mock_service/gmail/data/inbox.json",
))

PORT = int(os.environ.get("PORT", "9104"))

# In-memory state
_emails: list[dict[str, Any]] = []
_audit_log: list[dict[str, Any]] = []
_sent_messages: list[dict[str, Any]] = []


def _load_fixtures() -> None:
    """Load email fixtures and shift dates so the earliest email is ~20 hours ago."""
    global _emails
    with open(FIXTURES_PATH) as f:
        raw = json.load(f)

    # Support both flat array and nested {"_meta": ..., "messages": [...]} format
    if isinstance(raw, dict) and "messages" in raw:
        _emails = raw["messages"]
    else:
        _emails = raw

    if not _emails:
        return

    # Find the earliest date and shift to recent
    dates = []
    for e in _emails:
        dates.append(datetime.fromisoformat(e["date"].replace("Z", "+00:00")))
    earliest = min(dates)

    target = datetime.now(timezone.utc) - timedelta(hours=20)
    delta = target - earliest

    for e in _emails:
        old_dt = datetime.fromisoformat(e["date"].replace("Z", "+00:00"))
        new_dt = old_dt + delta
        e["date"] = new_dt.strftime("%Y-%m-%dT%H:%M:%SZ")


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


class ListMessagesRequest(BaseModel):
    days_back: int = 7
    max_results: int = 20


class GetMessageRequest(BaseModel):
    message_id: str


class SendMessageRequest(BaseModel):
    to: str
    subject: str
    body: str


# --- Endpoints ---


@app.get("/gmail/health")
def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


@app.post("/gmail/messages")
def list_messages(req: ListMessagesRequest | None = None) -> dict[str, Any]:
    """List messages in the inbox."""
    if req is None:
        req = ListMessagesRequest()
    cutoff = datetime.now(timezone.utc) - timedelta(days=req.days_back)
    results = []
    for email in _emails:
        email_dt = datetime.fromisoformat(email["date"].replace("Z", "+00:00"))
        if email_dt >= cutoff:
            results.append({
                "message_id": email["message_id"],
                "from": email["from"],
                "to": email.get("to", ""),
                "subject": email["subject"],
                "date": email["date"],
                "is_read": email.get("is_read", False),
                "labels": email.get("labels", []),
            })
    results = results[: req.max_results]
    resp = {"messages": results, "total": len(results)}
    _log_call("/gmail/messages", req.model_dump(), resp)
    return resp


@app.post("/gmail/messages/get")
def get_message(req: GetMessageRequest) -> dict[str, Any]:
    """Get a specific email message by ID."""
    for email in _emails:
        if email["message_id"] == req.message_id:
            resp = copy.deepcopy(email)
            _log_call("/gmail/messages/get", req.model_dump(), resp)
            return resp

    resp = {"error": f"Message {req.message_id} not found"}
    _log_call("/gmail/messages/get", req.model_dump(), resp)
    return resp


@app.post("/gmail/send")
def send_message(req: SendMessageRequest) -> dict[str, Any]:
    """Send an email (recorded for audit)."""
    msg = {
        "to": req.to,
        "subject": req.subject,
        "body": req.body,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    _sent_messages.append(msg)
    resp = {"status": "sent", "message": msg}
    _log_call("/gmail/send", req.model_dump(), resp)
    return resp


@app.get("/gmail/audit")
def get_audit() -> dict[str, Any]:
    """Return all API calls and sent messages for grader inspection."""
    return {
        "calls": _audit_log,
        "sent_messages": _sent_messages,
    }


@app.post("/gmail/reset")
def reset_state() -> dict[str, str]:
    """Reset state between trials."""
    global _audit_log, _sent_messages
    _audit_log = []
    _sent_messages = []
    _load_fixtures()
    return {"status": "reset"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
