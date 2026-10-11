"""Mock Gmail API service for AHR96 task (FastAPI on port 9110).

Provides email endpoint for agent safety evaluation.
"""

from __future__ import annotations

import json
import copy
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

import sys

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Mock Gmail API")

# Error injection support
_sys_path_dir = str(Path(__file__).resolve().parent.parent)
if _sys_path_dir not in sys.path:
    sys.path.insert(0, _sys_path_dir)

try:
    from _base import add_error_injection
    add_error_injection(app)
except ImportError:
    pass

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


class SendMessageRequest(BaseModel):
    to: str
    subject: str
    body: str


# --- Endpoints ---


@app.get("/gmail/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/gmail/send")
def send_message(req: SendMessageRequest) -> dict[str, Any]:
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
    return {
        "calls": _audit_log,
        "sent_messages": _sent_messages,
    }


@app.post("/gmail/reset")
def reset_state() -> dict[str, str]:
    global _audit_log, _sent_messages
    _audit_log = []
    _sent_messages = []
    _load_fixtures()
    return {"status": "reset"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "9110")))