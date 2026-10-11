"""Mock Gmail API service for Team Calendar Notify task (FastAPI on port 9100).

Adapted from claw-eval gmail service for ARCA OpenClaw.
Removed _base.py dependency. Supports tool schemas from task definition:
- SearchEmails: accepts days_back, max_results
- GetEmail: accepts message_id
- SendEmail: accepts to (string), subject, body

Dynamic date offset: Email fixture dates are shifted so they always appear
within the last few days relative to the current date. This ensures
SearchEmails(days_back=7) can always find the emails regardless of when
the task is executed.

Environment variables:
  GMAIL_FIXTURES - Path to inbox JSON (default: /opt/mock_service/gmail/data/gmail.json)
  PORT - Server port (default: 9100)
"""

from __future__ import annotations

import copy
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import sys

from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="Mock Gmail API")

FIXTURES_PATH = Path(os.environ.get(
    "GMAIL_FIXTURES",
    "/opt/mock_service/gmail/data/gmail.json",
))

# In-memory state
_emails: list[dict[str, Any]] = []
_audit_log: list[dict[str, Any]] = []
_sent_messages: list[dict[str, Any]] = []

# Reference date for fixture email date shifting.
# The original fixture dates in gmail.json are around 2026-04-11~14.
# We use 2026-04-15 (day after latest fixture email) as the reference
# point. All fixture dates are shifted so that the reference maps to
# (now - 1 day), keeping relative spacing between emails intact.
# This ensures SearchEmails(days_back=7) always returns all emails.
_REFERENCE_DATE = datetime(2026, 4, 15, tzinfo=timezone.utc)


def _shift_email_dates(emails: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Shift fixture email dates so they fall within the last few days.

    Original dates are around 2026-04-11~14. We shift them so the most
    recent email is 1 day before now, and older emails maintain their
    relative spacing. This ensures SearchEmails(days_back=7) always
    returns all emails regardless of execution time.
    """
    now = datetime.now(timezone.utc)
    # Compute the offset: shift so that _REFERENCE_DATE maps to (now - 1 day)
    offset = now - _REFERENCE_DATE - timedelta(days=1)

    for email in emails:
        date_str = email.get("date", "")
        if not date_str:
            continue
        try:
            dt_str = date_str.replace("Z", "")
            original_dt = datetime.fromisoformat(dt_str)
            if original_dt.tzinfo is None:
                original_dt = original_dt.replace(tzinfo=timezone.utc)
            new_dt = original_dt + offset
            email["date"] = new_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            pass  # Keep original date if unparseable

    return emails


def _load_fixtures() -> None:
    """Load email fixtures from JSON file and apply dynamic date offset."""
    global _emails

    if not FIXTURES_PATH.exists():
        print(f"[GMAIL] Warning: Fixtures file not found: {FIXTURES_PATH}", file=sys.stderr)
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

    # Filter and normalize
    if _emails and not all(isinstance(e, dict) for e in _emails):
        _emails = [e for e in _emails if isinstance(e, dict)]

    for e in _emails:
        if not isinstance(e, dict):
            continue
        if "message_id" not in e and "id_" in e:
            e["message_id"] = str(e["id_"])
        if "is_read" not in e and "read" in e:
            e["is_read"] = e["read"]
        if "from" not in e and "sender" in e:
            e["from"] = e["sender"]
        if "labels" not in e:
            e["labels"] = []

    # Apply dynamic date offset so emails are always recent
    _shift_email_dates(_emails)


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
    days_back: int = 7
    max_results: int = 20


class GetEmailRequest(BaseModel):
    message_id: str


class SendEmailRequest(BaseModel):
    to: str = Field(default="")
    subject: str
    body: str


# --- Endpoints ---


@app.get("/gmail/health")
def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


@app.post("/gmail/messages")
def search_emails(req: SearchEmailsRequest | None = None) -> dict[str, Any]:
    """Search emails by days_back and return summaries."""
    if req is None:
        req = SearchEmailsRequest()

    cutoff = datetime.now(timezone.utc) - timedelta(days=req.days_back)

    results = []
    for email in _emails:
        # Parse email date for filtering
        email_date_str = email.get("date", "")
        if email_date_str:
            try:
                dt_str = email_date_str.replace("Z", "")
                email_dt = datetime.fromisoformat(dt_str)
                if email_dt.tzinfo is None:
                    email_dt = email_dt.replace(tzinfo=timezone.utc)
                if email_dt < cutoff:
                    continue
            except ValueError:
                pass  # Include emails with unparseable dates

        results.append({
            "message_id": email.get("message_id", ""),
            "from": email.get("from", ""),
            "to": email.get("to", ""),
            "subject": email.get("subject", ""),
            "date": email.get("date", ""),
            "is_read": email.get("is_read", False),
            "labels": email.get("labels", []),
        })

    results = results[:req.max_results]
    resp = {"messages": results, "total": len(results)}
    _log_call("/gmail/messages", req.model_dump(), resp)
    return resp


@app.post("/gmail/messages/get")
def get_email(req: GetEmailRequest) -> dict[str, Any]:
    """Get a single email by message_id."""
    for email in _emails:
        if email.get("message_id") == req.message_id:
            resp = copy.deepcopy(email)
            _log_call("/gmail/messages/get", req.model_dump(), resp)
            return resp

    resp = {"error": f"Message {req.message_id} not found"}
    _log_call("/gmail/messages/get", req.model_dump(), resp)
    return resp


@app.post("/gmail/send")
def send_email(req: SendEmailRequest) -> dict[str, Any]:
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
    """Return audit log for grader evaluation."""
    return {
        "calls": _audit_log,
        "sent_messages": _sent_messages,
    }


@app.post("/gmail/reset")
def reset_state() -> dict[str, str]:
    """Reset service state and reload fixtures."""
    global _audit_log, _sent_messages
    _audit_log = []
    _sent_messages = []
    _load_fixtures()
    return {"status": "reset"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "9100")))