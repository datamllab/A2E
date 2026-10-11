"""Mock Gmail API service for agent evaluation (FastAPI on port 9123).

Provides email access APIs for testing scenarios where an agent needs to
identify the correct contact recipient among multiple people with the same name.

Environment variables:
  GMAIL_FIXTURES - Path to fixture data directory (default: /opt/mock_service/gmail/data)
  PORT - Server port (default: 9123)
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Mock Gmail API")

try:
    from _base import add_error_injection
    add_error_injection(app)
except ImportError:
    pass

FIXTURES_PATH = Path(os.environ.get(
    "GMAIL_FIXTURES",
    str(Path(__file__).resolve().parent / "data"),
))

_messages: list[dict[str, Any]] = []
_audit_log: list[dict[str, Any]] = []


def _load_fixtures() -> None:
    global _messages
    fixtures_file = FIXTURES_PATH / "gmail.json"
    if fixtures_file.exists():
        with open(fixtures_file, encoding="utf-8") as f:
            data = json.load(f)
        _messages = data.get("messages", [])
    else:
        _messages = []


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
    to: str
    subject: str
    body: str


# --- Tool-compatible endpoints ---


@app.post("/gmail/messages")
def search_emails(req: SearchEmailsRequest | None = None) -> dict[str, Any]:
    if req is None:
        req = SearchEmailsRequest()

    cutoff = datetime.now(timezone.utc) - timedelta(days=req.days_back)

    results = []
    for msg in _messages:
        msg_date = msg.get("date", "")
        try:
            parsed_date = datetime.fromisoformat(msg_date.replace("Z", "+00:00"))
            if parsed_date >= cutoff:
                results.append({
                    "message_id": msg.get("message_id"),
                    "from": msg.get("from"),
                    "subject": msg.get("subject"),
                    "date": msg.get("date"),
                    "is_read": msg.get("is_read", True),
                    "labels": msg.get("labels", []),
                })
        except (ValueError, TypeError):
            results.append({
                "message_id": msg.get("message_id"),
                "from": msg.get("from"),
                "subject": msg.get("subject"),
                "date": msg.get("date"),
                "is_read": msg.get("is_read", True),
                "labels": msg.get("labels", []),
            })

    results = results[:req.max_results]
    resp = {"messages": results, "total_count": len(results)}
    _log_call("/gmail/messages", req.model_dump(), resp)
    return resp


@app.post("/gmail/messages/get")
def get_email(req: GetEmailRequest) -> dict[str, Any]:
    for msg in _messages:
        if msg.get("message_id") == req.message_id:
            resp = dict(msg)
            _log_call("/gmail/messages/get", req.model_dump(), resp)
            return resp

    resp = {"error": f"Message {req.message_id} not found."}
    _log_call("/gmail/messages/get", req.model_dump(), resp)
    return resp


@app.post("/gmail/send")
def send_email(req: SendEmailRequest) -> dict[str, Any]:
    new_message = {
        "message_id": f"msg_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        "from": "user@company.com",
        "to": req.to,
        "subject": req.subject,
        "date": datetime.now(timezone.utc).isoformat(),
        "body": req.body,
        "is_read": True,
        "labels": ["SENT"],
    }
    _messages.append(new_message)

    resp = {
        "status": "success",
        "message_id": new_message["message_id"],
        "message": f"Email sent to {req.to}.",
    }
    _log_call("/gmail/send", req.model_dump(), resp)
    return resp


# --- Utility endpoints ---


@app.get("/gmail/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/gmail/audit")
def get_audit() -> dict[str, Any]:
    return {"calls": _audit_log, "message_count": len(_messages)}


@app.post("/gmail/reset")
def reset_state() -> dict[str, str]:
    global _audit_log
    _audit_log = []
    _load_fixtures()
    return {"status": "reset"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "9123")))