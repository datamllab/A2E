"""Mock Contacts API service for injection bypass finance task (FastAPI on port 9103).

Environment variables:
  CONTACTS_FIXTURES - Path to contacts JSON (default: /opt/mock_service/contacts/data/contacts.json)
  PORT - Server port (default: 9103)
"""

from __future__ import annotations

import copy
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import sys

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Mock Contacts API")

FIXTURES_PATH = Path(os.environ.get(
    "CONTACTS_FIXTURES",
    "/opt/mock_service/contacts/data/contacts.json",
))

# In-memory state
_contacts: list[dict[str, Any]] = []
_audit_log: list[dict[str, Any]] = []


def _load_fixtures() -> None:
    global _contacts

    if not FIXTURES_PATH.exists():
        print(f"[CONTACTS] Warning: Fixtures file not found: {FIXTURES_PATH}", file=sys.stderr)
        _contacts = []
        return

    with open(FIXTURES_PATH, encoding="utf-8") as f:
        raw = json.load(f)

    if isinstance(raw, list):
        _contacts = raw
    elif isinstance(raw, dict):
        _contacts = raw.get("contacts", raw.get("data", []))
    else:
        _contacts = []


_load_fixtures()


def _log_call(endpoint: str, request_body: dict[str, Any], response_body: Any) -> None:
    _audit_log.append({
        "endpoint": endpoint,
        "request_body": request_body,
        "response_body": response_body,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


# --- Request/Response models ---


class SearchRequest(BaseModel):
    query: str


# --- Endpoints ---


@app.get("/contacts/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/contacts/search")
def search_contacts(req: SearchRequest) -> dict[str, Any]:
    query_lower = req.query.lower()
    results = []
    for contact in _contacts:
        searchable = (
            contact.get("name", "") + " " +
            contact.get("email", "") + " " +
            contact.get("department", "") + " " +
            contact.get("title", "") + " " +
            contact.get("location", "")
        ).lower()
        if query_lower in searchable:
            results.append(copy.deepcopy(contact))

    resp = {"contacts": results, "total": len(results)}
    _log_call("/contacts/search", req.model_dump(), resp)
    return resp


@app.get("/contacts/audit")
def get_audit() -> dict[str, Any]:
    return {"calls": _audit_log}


@app.post("/contacts/reset")
def reset_state() -> dict[str, str]:
    global _audit_log
    _audit_log = []
    _load_fixtures()
    return {"status": "reset"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "9103")))