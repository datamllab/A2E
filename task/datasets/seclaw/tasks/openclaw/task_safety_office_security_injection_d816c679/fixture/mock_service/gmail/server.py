"""Mock Gmail API service for ARCA OpenClaw task evaluation.

Provides email management APIs matching the MCP tool schema:
- POST /gmail/messages       (list inbox messages)
- POST /gmail/messages/get   (get message details)
- GET  /gmail/health         (health check)
- GET  /gmail/audit          (grader inspection)
- POST /gmail/reset          (state reset between trials)

Adapted from claw-eval TBC_L1_02_office_security_injection task.
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

# Configuration - use environment variable or default bundled location
FIXTURES_PATH = Path(os.environ.get(
    "GMAIL_FIXTURES",
    str(Path(__file__).resolve().parent / "data" / "inbox.json"),
))

# In-memory state
_emails: list[dict[str, Any]] = []
_audit_log: list[dict[str, Any]] = []


def _load_fixtures() -> None:
    """Load email fixtures and shift dates so the earliest email is ~20 hours ago."""
    global _emails

    if not FIXTURES_PATH.exists():
        print(f"[GMAIL] Warning: Fixtures file not found: {FIXTURES_PATH}")
        _emails = []
        return

    with open(FIXTURES_PATH) as f:
        raw = json.load(f)

    if isinstance(raw, dict):
        if "messages" in raw:
            _emails = raw["messages"]
        elif "emails" in raw:
            _emails = raw["emails"]
        else:
            _emails = []
    else:
        _emails = raw

    if _emails and not all(isinstance(e, dict) for e in _emails):
        _emails = [e for e in _emails if isinstance(e, dict)]

    if not _emails:
        return

    dates = []
    for e in _emails:
        if not isinstance(e, dict):
            continue
        date_str = e.get("date") or e.get("timestamp")
        if date_str:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            if dt.tzinfo is not None:
                dt = dt.replace(tzinfo=None)
            dates.append(dt)
    if not dates:
        return
    earliest = min(dates)

    target = datetime.now() - timedelta(hours=20)
    delta = target - earliest

    for e in _emails:
        if not isinstance(e, dict):
            continue
        date_str = e.get("date") or e.get("timestamp")
        if date_str:
            old_dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            if old_dt.tzinfo is not None:
                old_dt = old_dt.replace(tzinfo=None)
            new_dt = old_dt + delta
            e["date"] = new_dt.strftime("%Y-%m-%dT%H:%M:%S")
        if "message_id" not in e and "id_" in e:
            e["message_id"] = str(e["id_"])
        if "is_read" not in e and "read" in e:
            e["is_read"] = e["read"]
        if "from" not in e and "sender" in e:
            e["from"] = e["sender"]
        if "labels" not in e:
            e["labels"] = []


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


# --- Endpoints ---


@app.get("/gmail/health")
def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


@app.post("/gmail/messages")
def list_messages(req: ListMessagesRequest | None = None) -> dict[str, Any]:
    """List emails from inbox, filtered by recency."""
    if req is None:
        req = ListMessagesRequest()

    cutoff = datetime.now() - timedelta(days=req.days_back)
    results = []
    for email in _emails:
        date_str = email.get("date") or email.get("timestamp", "")
        email_date = datetime.fromisoformat(date_str.replace("Z", "") if "Z" in date_str else date_str)
        if email_date.tzinfo is not None:
            email_date = email_date.replace(tzinfo=None)
        if email_date >= cutoff:
            results.append({
                "message_id": email["message_id"],
                "from": email["from"],
                "subject": email["subject"],
                "date": email["date"],
                "is_read": email["is_read"],
                "labels": email["labels"],
            })
    results = results[: req.max_results]

    resp = {"messages": results, "total": len(results)}
    _log_call("/gmail/messages", req.model_dump(), resp)
    return resp


@app.post("/gmail/messages/get")
def get_message(req: GetMessageRequest) -> dict[str, Any]:
    """Get a single email by message_id."""
    for email in _emails:
        if email["message_id"] == req.message_id:
            resp = copy.deepcopy(email)
            _log_call("/gmail/messages/get", req.model_dump(), resp)
            return resp

    resp = {"error": f"Message {req.message_id} not found"}
    _log_call("/gmail/messages/get", req.model_dump(), resp)
    return resp


@app.get("/gmail/audit")
def get_audit() -> dict[str, Any]:
    """Return all API calls for grader inspection."""
    return {
        "calls": _audit_log,
    }


@app.post("/gmail/reset")
def reset_state() -> dict[str, str]:
    """Reset state between trials."""
    global _audit_log
    _audit_log = []
    _load_fixtures()
    return {"status": "reset"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "9100")))