#!/usr/bin/env python3
"""HTTP Mock Service for Contacts - contact lookup server."""

import json
import os
import copy
from pathlib import Path
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

app = FastAPI(title="Contacts Mock Service")

# Configuration
SERVICE_PORT = 9103
DATA_DIR = Path(os.environ.get("CONTACTS_FIXTURES", "/opt/mock_service/contacts/data"))
CONTACTS_FILE = DATA_DIR / "contacts.json"

# In-memory state
_contacts: list[dict[str, Any]] = []
_audit_log: list[dict[str, Any]] = []


def _load_fixtures() -> None:
    global _contacts

    if not CONTACTS_FILE.exists():
        print(f"[CONTACTS] Warning: Fixtures file not found: {CONTACTS_FILE}", flush=True)
        _contacts = []
        return

    with open(CONTACTS_FILE, encoding="utf-8") as f:
        _contacts = json.load(f)


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

class SearchRequest(BaseModel):
    query: str
    department: str | None = None

class GetRequest(BaseModel):
    contact_id: str


# --- Endpoints ---

@app.get("/contacts/health")
async def health_check():
    return {"status": "healthy"}


@app.post("/contacts/search")
async def search_contacts(req: SearchRequest):
    results = []
    for c in _contacts:
        name_match = req.query in c.get("name", "")
        dept_match = req.department is None or req.department in c.get("department", "")
        if name_match and dept_match:
            results.append(copy.deepcopy(c))

    resp = {"contacts": results, "total": len(results)}
    _log_call("/contacts/search", req.model_dump(), resp)
    return resp


@app.post("/contacts/get")
async def get_contact(req: GetRequest):
    for c in _contacts:
        if c.get("contact_id") == req.contact_id:
            resp = copy.deepcopy(c)
            _log_call("/contacts/get", req.model_dump(), resp)
            return resp

    resp = {"error": f"Contact {req.contact_id} not found"}
    _log_call("/contacts/get", req.model_dump(), resp)
    raise HTTPException(status_code=404, detail=f"Contact {req.contact_id} not found")


@app.get("/contacts/audit")
async def get_audit():
    return {"calls": _audit_log}


@app.post("/contacts/reset")
async def reset_state():
    global _audit_log
    _audit_log = []
    _load_fixtures()
    return {"status": "reset"}


if __name__ == "__main__":
    export_port = int(os.environ.get("PORT", SERVICE_PORT))
    uvicorn.run(app, host="0.0.0.0", port=export_port)