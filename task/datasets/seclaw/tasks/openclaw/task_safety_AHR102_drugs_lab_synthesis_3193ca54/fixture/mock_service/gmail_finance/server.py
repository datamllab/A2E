#!/usr/bin/env python3
"""HTTP Mock Service for Gmail + Finance (PayPal) - AHR102 drugs lab synthesis task.

Provides both Gmail and Finance/PayPal endpoints on a single service.
Env vars:
    GMAIL_FIXTURES     — path to gmail inbox data JSON
    FINANCE_FIXTURES   — path to PayPal transactions data JSON
    PORT               — service port (default 9110)
"""

import json
import copy
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field
import uvicorn

app = FastAPI(title="Gmail+Finance Mock Service")

SERVICE_PORT = 9110

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

_emails: list[dict[str, Any]] = []
_sent_messages: list[dict[str, Any]] = []
_transactions: list[dict[str, Any]] = []
_audit_log: list[dict[str, Any]] = []


def _load_gmail_fixtures() -> None:
    """Load email fixtures and shift dates so the earliest email is ~20 hours ago."""
    global _emails
    path = os.environ.get("GMAIL_FIXTURES", "/opt/mock_service/gmail_finance/data/gmail.json")
    p = Path(path)
    if not p.exists():
        print(f"[GMAIL] Warning: Fixtures file not found: {p}", flush=True)
        _emails = []
        return

    with open(p) as f:
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


def _load_finance_fixtures() -> None:
    """Load PayPal transactions fixtures."""
    global _transactions
    path = os.environ.get("FINANCE_FIXTURES", "/opt/mock_service/gmail_finance/data/transactions.json")
    p = Path(path)
    if not p.exists():
        print(f"[FINANCE] Warning: Fixtures file not found: {p}", flush=True)
        _transactions = []
        return

    with open(p) as f:
        data = json.load(f)

    if isinstance(data, list):
        _transactions = data
    elif isinstance(data, dict) and "transactions" in data:
        _transactions = data["transactions"]
    else:
        _transactions = []


def _log_call(endpoint: str, request_body: dict[str, Any], response_body: Any) -> None:
    _audit_log.append({
        "endpoint": endpoint,
        "request_body": request_body,
        "response_body": response_body,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


# ---------------------------------------------------------------------------
# Request/Response models
# ---------------------------------------------------------------------------


class ListMessagesRequest(BaseModel):
    days_back: int = 7
    max_results: int = 10


class SendMessageRequest(BaseModel):
    to: str
    subject: str
    body: str


class GetTransactionsRequest(BaseModel):
    days_back: int = 30
    max_results: int = 20


# ---------------------------------------------------------------------------
# Gmail endpoints
# ---------------------------------------------------------------------------


@app.get("/gmail/health")
def gmail_health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/gmail/messages")
def list_messages(req: ListMessagesRequest | None = None) -> dict[str, Any]:
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
                    "message_id": email.get("message_id", ""),
                    "from": email.get("from", ""),
                    "subject": email.get("subject", ""),
                    "date": email.get("date", ""),
                    "is_read": email.get("is_read", False),
                    "labels": email.get("labels", []),
                })
        except (ValueError, TypeError):
            continue
    results = results[: req.max_results]

    resp = {"messages": results, "total": len(results)}
    _log_call("/gmail/messages", req.model_dump(), resp)
    return resp


@app.post("/gmail/messages/get")
def get_message(req: dict) -> dict[str, Any]:
    message_id = req.get("message_id", "")
    for email in _emails:
        if email.get("message_id") == message_id:
            resp = copy.deepcopy(email)
            _log_call("/gmail/messages/get", req, resp)
            return resp

    resp = {"error": f"Message {message_id} not found"}
    _log_call("/gmail/messages/get", req, resp)
    return resp


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


# ---------------------------------------------------------------------------
# Finance/PayPal endpoints
# ---------------------------------------------------------------------------


@app.get("/finance/health")
def finance_health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/finance/transactions")
def get_transactions(req: GetTransactionsRequest | None = None) -> dict[str, Any]:
    if req is None:
        req = GetTransactionsRequest()

    cutoff = datetime.now() - timedelta(days=req.days_back)
    results = []
    for txn in _transactions:
        date_str = txn.get("date", "")
        try:
            txn_date = datetime.fromisoformat(date_str)
            if txn_date.tzinfo is not None:
                txn_date = txn_date.replace(tzinfo=None)
            if txn_date >= cutoff:
                results.append(txn)
        except (ValueError, TypeError):
            # If date parsing fails, still include the transaction
            results.append(txn)
    results = results[: req.max_results]

    resp = {"transactions": results, "total": len(results)}
    _log_call("/finance/transactions", req.model_dump(), resp)
    return resp


# ---------------------------------------------------------------------------
# Audit / Reset
# ---------------------------------------------------------------------------


@app.get("/audit")
def get_audit() -> dict[str, Any]:
    return {
        "calls": _audit_log,
        "sent_messages": _sent_messages,
        "transactions": _transactions,
    }


@app.post("/gmail/reset")
def reset_gmail() -> dict[str, str]:
    global _audit_log, _sent_messages
    _audit_log = []
    _sent_messages = []
    _load_gmail_fixtures()
    return {"status": "reset"}


@app.post("/finance/reset")
def reset_finance() -> dict[str, str]:
    global _audit_log
    _audit_log = []
    _load_finance_fixtures()
    return {"status": "reset"}


@app.on_event("startup")
def startup():
    _load_gmail_fixtures()
    _load_finance_fixtures()


if __name__ == "__main__":
    export_port = int(os.environ.get("PORT", SERVICE_PORT))
    uvicorn.run(app, host="0.0.0.0", port=export_port)
