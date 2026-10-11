"""Mock Gmail API service for agent evaluation (FastAPI on port 9100)."""

from __future__ import annotations

import json
import copy
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="Mock Gmail API")

FIXTURES_PATH = Path(os.environ.get(
    "GMAIL_FIXTURES",
    str(Path(__file__).resolve().parent / "data" / "inbox.json"),
))

# In-memory state
_emails: list[dict[str, Any]] = []
_audit_log: list[dict[str, Any]] = []
_sent_messages: list[dict[str, Any]] = []


def _load_fixtures() -> None:
    """Load email fixtures and shift dates so the earliest email is ~20 hours ago."""
    global _emails

    if not FIXTURES_PATH.exists():
        print(f"[GMAIL] Warning: Fixtures file not found: {FIXTURES_PATH}", file=__import__('sys').stderr)
        _emails = []
        return

    with open(FIXTURES_PATH, encoding="utf-8") as f:
        data = json.load(f)

    # Support both list and dict with "messages" key
    if isinstance(data, dict) and "messages" in data:
        _emails = data["messages"]
    else:
        _emails = data

    if not _emails:
        return

    # Find the earliest date in the fixtures
    dates = []
    for e in _emails:
        dates.append(datetime.fromisoformat(e["date"].replace("Z", "+00:00")))
    earliest = min(dates)

    # Shift so the earliest email is ~20 hours ago
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


class SearchEmailsRequest(BaseModel):
    keywords: list[str] | None = Field(None, description="Keywords to search for in email subject and body")
    max_results: int = Field(10, description="Maximum number of results to return")


class GetEmailRequest(BaseModel):
    message_id: str = Field(..., description="The message ID to retrieve")


class SendMessageRequest(BaseModel):
    to: str = Field(..., description="Recipient email address")
    subject: str = Field(..., description="Email subject line")
    body: str = Field(..., description="Email body content")


# --- Endpoints ---


@app.get("/gmail/health")
def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/gmail/audit")
def get_audit() -> dict[str, Any]:
    """Return all API calls for grader inspection."""
    return {
        "calls": _audit_log,
        "sent_messages": _sent_messages,
    }


@app.post("/gmail/searchemails")
def search_emails(req: SearchEmailsRequest | None = None) -> dict[str, Any]:
    """Search emails by keywords. Returns list of matching emails with summary info."""
    if req is None:
        req = SearchEmailsRequest()

    keywords = req.keywords or []
    results = []
    for email in _emails:
        # Search in subject and body
        text_to_search = (email.get("subject", "") + " " + email.get("body", "")).lower()
        if any(kw.lower() in text_to_search for kw in keywords):
            results.append({
                "message_id": email["message_id"],
                "from": email["from"],
                "subject": email["subject"],
                "date": email["date"],
                "is_read": email.get("is_read", True),
                "labels": email.get("labels", ["INBOX"]),
            })
    results = results[: req.max_results]

    resp = {"messages": results, "total": len(results)}
    _log_call("/gmail/searchemails", req.model_dump(), resp)
    return resp


@app.post("/gmail/messages")
def list_messages(days_back: int = 7, max_results: int = 20) -> dict[str, Any]:
    """List emails from inbox, filtered by recency."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
    results = []
    for email in _emails:
        email_date = datetime.fromisoformat(email["date"].replace("Z", "+00:00"))
        if email_date >= cutoff:
            results.append({
                "message_id": email["message_id"],
                "from": email["from"],
                "subject": email["subject"],
                "date": email["date"],
                "is_read": email.get("is_read", True),
                "labels": email.get("labels", ["INBOX"]),
            })
    results = results[:max_results]

    resp = {"messages": results, "total": len(results)}
    _log_call("/gmail/messages", {"days_back": days_back, "max_results": max_results}, resp)
    return resp


@app.post("/gmail/messages/get")
def get_email_by_id(req: GetEmailRequest) -> dict[str, Any]:
    """Get full email content by message_id."""
    for email in _emails:
        if email["message_id"] == req.message_id:
            resp = copy.deepcopy(email)
            _log_call("/gmail/messages/get", req.model_dump(), resp)
            return resp

    resp = {"error": f"Message {req.message_id} not found"}
    _log_call("/gmail/messages/get", req.model_dump(), resp)
    return resp


@app.post("/gmail/reademail")
def read_email(req: GetEmailRequest) -> dict[str, Any]:
    """Get a single email by message_id (alias for /gmail/messages/get)."""
    for email in _emails:
        if email["message_id"] == req.message_id:
            resp = copy.deepcopy(email)
            _log_call("/gmail/reademail", req.model_dump(), resp)
            return resp

    resp = {"error": f"Message {req.message_id} not found"}
    _log_call("/gmail/reademail", req.model_dump(), resp)
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

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "9100")))