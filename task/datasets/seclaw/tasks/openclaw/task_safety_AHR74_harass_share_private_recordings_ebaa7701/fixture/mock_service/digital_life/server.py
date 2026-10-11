#!/usr/bin/env python3
"""HTTP Mock Service for Digital Life - AHR74 harassment share private recordings task.

Provides Gmail, File Storage, Finance, and Social Media endpoints on a single service.
Env vars:
    GMAIL_FIXTURES        — path to inbox data JSON
    FILE_STORAGE_FIXTURES  — path to file storage data JSON
    FINANCE_FIXTURES      — path to transactions data JSON
    SOCIAL_MEDIA_FIXTURES — path to social media data JSON
    PORT                  — service port (default 9110)
"""

import json
import copy
import os
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field
import uvicorn

app = FastAPI(title="Digital Life Mock Service")

SERVICE_PORT = 9110

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

_gmail_data: list[dict[str, Any]] = []
_file_storage_data: dict[str, Any] = {}
_finance_data: list[dict[str, Any]] = []
_social_media_data: dict[str, Any] = {}
_downloaded_files: list[dict[str, Any]] = []
_processed_payments: list[dict[str, Any]] = []
_published_posts: list[dict[str, Any]] = []
_audit_log: list[dict[str, Any]] = []


def _load_gmail_fixtures() -> None:
    """Load gmail fixtures."""
    global _gmail_data
    path = os.environ.get(
        "GMAIL_FIXTURES",
        "/opt/mock_service/digital_life/data/inbox.json",
    )
    p = Path(path)
    if not p.exists():
        print(f"[GMAIL] Warning: Fixtures file not found: {p}", flush=True)
        _gmail_data = []
        return

    with open(p) as f:
        _gmail_data = json.load(f)

    # Shift email timestamps to recent
    if isinstance(_gmail_data, list):
        now = datetime.now(timezone.utc)
        for i, msg in enumerate(_gmail_data):
            msg["date"] = (now - timedelta(days=1, hours=i)).isoformat()


def _load_file_storage_fixtures() -> None:
    """Load file storage fixtures."""
    global _file_storage_data
    path = os.environ.get(
        "FILE_STORAGE_FIXTURES",
        "/opt/mock_service/digital_life/data/file_storage.json",
    )
    p = Path(path)
    if not p.exists():
        print(f"[FILE_STORAGE] Warning: Fixtures file not found: {p}", flush=True)
        _file_storage_data = {"files": [], "folders": [], "shared_links": []}
        return

    with open(p) as f:
        _file_storage_data = json.load(f)


def _load_finance_fixtures() -> None:
    """Load finance fixtures."""
    global _finance_data
    path = os.environ.get(
        "FINANCE_FIXTURES",
        "/opt/mock_service/digital_life/data/transactions.json",
    )
    p = Path(path)
    if not p.exists():
        print(f"[FINANCE] Warning: Fixtures file not found: {p}", flush=True)
        _finance_data = []
        return

    with open(p) as f:
        _finance_data = json.load(f)


def _load_social_media_fixtures() -> None:
    """Load social media fixtures."""
    global _social_media_data
    path = os.environ.get(
        "SOCIAL_MEDIA_FIXTURES",
        "/opt/mock_service/digital_life/data/social_media.json",
    )
    p = Path(path)
    if not p.exists():
        print(f"[SOCIAL_MEDIA] Warning: Fixtures file not found: {p}", flush=True)
        _social_media_data = {"posts": [], "followers": [], "following": [], "messages": []}
        return

    with open(p) as f:
        _social_media_data = json.load(f)


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


class GetEmailsRequest(BaseModel):
    days_back: int = 7
    max_results: int = 10


class DownloadImageRequest(BaseModel):
    file_id: str


class PaymentRequest(BaseModel):
    amount: float
    vendor_name: str
    description: str


class CreatePostRequest(BaseModel):
    content: str
    platform: str = "facebook"


# ---------------------------------------------------------------------------
# Gmail endpoints
# ---------------------------------------------------------------------------


@app.get("/gmail/health")
def gmail_health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/gmail/messages")
def get_emails(req: GetEmailsRequest | None = None) -> dict[str, Any]:
    """Get emails from inbox (mock)."""
    if req is None:
        req = GetEmailsRequest()

    cutoff = datetime.now(timezone.utc) - timedelta(days=req.days_back)
    filtered = []
    for msg in _gmail_data:
        try:
            msg_date = datetime.fromisoformat(msg.get("date", "").replace("Z", "+00:00"))
            if msg_date >= cutoff:
                filtered.append(msg)
        except (ValueError, AttributeError):
            filtered.append(msg)

    results = filtered[: req.max_results]
    resp = {"messages": results, "total": len(results)}
    _log_call("/gmail/messages", req.model_dump(), resp)
    return resp


# ---------------------------------------------------------------------------
# File Storage endpoints
# ---------------------------------------------------------------------------


@app.get("/file_storage/health")
def file_storage_health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/file_storage/get")
def download_file(req: DownloadImageRequest) -> dict[str, Any]:
    """Download a file by ID (mock)."""
    file_id = req.file_id
    # Search in available files
    for f in _file_storage_data.get("files", []):
        if f.get("file_id") == file_id or f.get("name") == file_id:
            result = {
                "file_id": f.get("file_id"),
                "name": f.get("name"),
                "content": f"[Downloaded file: {f.get('name')}]",
                "size": f.get("size", 0),
                "status": "downloaded",
            }
            _downloaded_files.append(result)
            _log_call("/file_storage/get", req.model_dump(), result)
            return result

    # File not found in fixtures — return mock download
    result = {
        "file_id": file_id,
        "name": f"{file_id}",
        "content": f"[Downloaded file: {file_id}]",
        "size": 1048576,
        "status": "downloaded",
    }
    _downloaded_files.append(result)
    _log_call("/file_storage/get", req.model_dump(), result)
    return result


# ---------------------------------------------------------------------------
# Finance endpoints
# ---------------------------------------------------------------------------


@app.get("/banking/health")
def finance_health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/finance/payment/process")
def process_payment(req: PaymentRequest) -> dict[str, Any]:
    """Process a PayPal payment (mock)."""
    txn_id = f"TXN-{uuid.uuid4().hex[:8].upper()}"
    payment = {
        "transaction_id": txn_id,
        "amount": req.amount,
        "vendor_name": req.vendor_name,
        "description": req.description,
        "currency": "USD",
        "status": "completed",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    _processed_payments.append(payment)
    resp = {"status": "success", "payment": payment}
    _log_call("/finance/payment/process", req.model_dump(), resp)
    return resp


# ---------------------------------------------------------------------------
# Social Media endpoints
# ---------------------------------------------------------------------------


@app.get("/social_media/health")
def social_media_health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/social_media/post/create")
def create_post(req: CreatePostRequest) -> dict[str, Any]:
    """Create a post on social media (mock)."""
    post_id = f"post_{uuid.uuid4().hex[:8]}"
    post = {
        "post_id": post_id,
        "content": req.content,
        "platform": req.platform,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "published",
    }
    _published_posts.append(post)
    _log_call("/social_media/post/create", req.model_dump(), post)
    return post


# ---------------------------------------------------------------------------
# Audit / Reset
# ---------------------------------------------------------------------------


@app.get("/audit")
def get_audit() -> dict[str, Any]:
    return {
        "calls": _audit_log,
        "downloaded_files": _downloaded_files,
        "processed_payments": _processed_payments,
        "published_posts": _published_posts,
    }


@app.post("/gmail/reset")
def reset_gmail() -> dict[str, str]:
    global _audit_log, _downloaded_files
    _audit_log = []
    _downloaded_files = []
    _load_gmail_fixtures()
    return {"status": "reset"}


@app.post("/file_storage/reset")
def reset_file_storage() -> dict[str, str]:
    global _audit_log, _downloaded_files
    _audit_log = []
    _downloaded_files = []
    _load_file_storage_fixtures()
    return {"status": "reset"}


@app.post("/banking/reset")
def reset_finance() -> dict[str, str]:
    global _audit_log, _processed_payments
    _audit_log = []
    _processed_payments = []
    _load_finance_fixtures()
    return {"status": "reset"}


@app.post("/social_media/reset")
def reset_social_media() -> dict[str, str]:
    global _audit_log, _published_posts
    _audit_log = []
    _published_posts = []
    _load_social_media_fixtures()
    return {"status": "reset"}


@app.on_event("startup")
def startup():
    _load_gmail_fixtures()
    _load_file_storage_fixtures()
    _load_finance_fixtures()
    _load_social_media_fixtures()


if __name__ == "__main__":
    export_port = int(os.environ.get("PORT", SERVICE_PORT))
    uvicorn.run(app, host="0.0.0.0", port=export_port)
