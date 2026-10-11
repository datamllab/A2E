#!/usr/bin/env python3
"""HTTP Mock Service for Gmail - email operations server."""

import json
import os
import copy
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import uvicorn

app = FastAPI(title="Gmail Mock Service")

# Configuration
SERVICE_PORT = 9100
DATA_DIR = Path(os.environ.get("GMAIL_FIXTURES", "/opt/mock_service/gmail/data"))
INBOX_FILE = DATA_DIR / "inbox.json"

# In-memory state
_emails: list[dict[str, Any]] = []
_audit_log: list[dict[str, Any]] = []
_sent_messages: list[dict[str, Any]] = []
_drafts: list[dict[str, Any]] = []


def _load_fixtures() -> None:
    """Load email fixtures and shift dates so the earliest email is recent."""
    global _emails

    if not INBOX_FILE.exists():
        print(f"[GMAIL] Warning: Fixtures file not found: {INBOX_FILE}", flush=True)
        _emails = []
        return

    with open(INBOX_FILE, encoding="utf-8") as f:
        raw = json.load(f)

    if isinstance(raw, dict):
        _emails = raw.get("messages", raw.get("emails", []))
    else:
        _emails = raw

    _emails = [e for e in _emails if isinstance(e, dict)]
    if not _emails:
        return

    # Shift dates so the earliest email is ~20 hours ago
    dates = []
    for e in _emails:
        date_str = e.get("date") or e.get("timestamp")
        if date_str:
            try:
                dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                if dt.tzinfo is not None:
                    dt = dt.replace(tzinfo=None)
                dates.append(dt)
            except (ValueError, TypeError):
                pass

    if dates:
        earliest = min(dates)
        target = datetime.now() - timedelta(hours=20)
        delta = target - earliest
        for e in _emails:
            date_str = e.get("date") or e.get("timestamp")
            if date_str:
                try:
                    old_dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                    if old_dt.tzinfo is not None:
                        old_dt = old_dt.replace(tzinfo=None)
                    e["date"] = (old_dt + delta).strftime("%Y-%m-%dT%H:%M:%S")
                except (ValueError, TypeError):
                    pass

    # Normalize fields
    for e in _emails:
        if "message_id" not in e and "id_" in e:
            e["message_id"] = str(e["id_"])
        if "is_read" not in e and "read" in e:
            e["is_read"] = e["read"]
        if "from" not in e and "sender" in e:
            e["from"] = e["sender"]
        if "labels" not in e:
            e["labels"] = []


def _log_call(endpoint: str, request_body: dict, response_body: Any) -> None:
    _audit_log.append({
        "endpoint": endpoint,
        "request_body": request_body,
        "response_body": response_body,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


@app.on_event("startup")
async def startup():
    _load_fixtures()


# --- Request models ---

class ListMessagesRequest(BaseModel):
    days_back: int = 7
    max_results: int = 20

class GetMessageRequest(BaseModel):
    message_id: str

class SendMessageRequest(BaseModel):
    to: str
    subject: str
    body: str

class SaveDraftRequest(BaseModel):
    to: str
    subject: str
    body: str
    reply_to_message_id: str | None = None


# --- Endpoints ---

@app.get("/gmail/health")
async def health_check():
    return {"status": "healthy"}


@app.post("/gmail/messages")
async def list_messages(req: ListMessagesRequest | None = None):
    if req is None:
        req = ListMessagesRequest()

    cutoff = datetime.now() - timedelta(days=req.days_back)
    results = []
    for email in _emails:
        date_str = email.get("date") or email.get("timestamp", "")
        try:
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
        except (ValueError, TypeError):
            pass

    results = results[: req.max_results]
    resp = {"messages": results, "total": len(results)}
    _log_call("/gmail/messages", req.model_dump(), resp)
    return resp


@app.post("/gmail/messages/get")
async def get_message(req: GetMessageRequest):
    for email in _emails:
        if email["message_id"] == req.message_id:
            resp = copy.deepcopy(email)
            _log_call("/gmail/messages/get", req.model_dump(), resp)
            return resp

    resp = {"error": f"Message {req.message_id} not found"}
    _log_call("/gmail/messages/get", req.model_dump(), resp)
    raise HTTPException(status_code=404, detail=f"Message {req.message_id} not found")


@app.post("/gmail/send")
async def send_message(req: SendMessageRequest):
    msg = {
        "to": req.to,
        "subject": req.subject,
        "body": req.body,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    _sent_messages.append(msg)
    resp = {"status": "sent", "message_id": f"sent_{len(_sent_messages):03d}", "to": req.to, "subject": req.subject}
    _log_call("/gmail/send", req.model_dump(), resp)
    return resp


@app.post("/gmail/drafts/save")
async def save_draft(req: SaveDraftRequest):
    draft = {
        "to": req.to,
        "subject": req.subject,
        "body": req.body,
        "reply_to_message_id": req.reply_to_message_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    _drafts.append(draft)
    resp = {"status": "draft_saved", "draft": draft}
    _log_call("/gmail/drafts/save", req.model_dump(), resp)
    return resp


@app.get("/gmail/audit")
async def get_audit():
    return {
        "calls": _audit_log,
        "sent_messages": _sent_messages,
        "drafts": _drafts,
    }


@app.post("/gmail/reset")
async def reset_state():
    global _audit_log, _sent_messages, _drafts
    _audit_log = []
    _sent_messages = []
    _drafts = []
    _load_fixtures()
    return {"status": "reset"}


if __name__ == "__main__":
    export_port = int(os.environ.get("PORT", SERVICE_PORT))
    uvicorn.run(app, host="0.0.0.0", port=export_port)