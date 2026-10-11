"""Contacts mock HTTP service."""

import json
import os
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel

app = FastAPI()

FIXTURES_PATH = os.environ.get("CONTACTS_FIXTURES", "/opt/mock_service/contacts/data/contacts.json")
_contacts = []
_audit_log = []


def _load_fixtures():
    global _contacts, _audit_log
    try:
        with open(FIXTURES_PATH) as f:
            _contacts = json.load(f)
    except Exception:
        _contacts = []
    _audit_log = []


def _log_call(tool_name: str, request_body: dict, response_body: dict):
    _audit_log.append({
        "timestamp": datetime.utcnow().isoformat(),
        "tool_name": tool_name,
        "request_body": request_body,
        "response_body": response_body,
    })


_load_fixtures()


class SearchRequest(BaseModel):
    query: str
    department: str = None

class GetRequest(BaseModel):
    contact_id: str


@app.post("/contacts/search")
def search_contacts(req: SearchRequest):
    query_lower = req.query.lower()
    results = []
    for c in _contacts:
        match = (
            query_lower in c.get("name", "").lower()
            or query_lower in c.get("department", "").lower()
            or query_lower in c.get("email", "").lower()
            or query_lower in c.get("title", "").lower()
        )
        if req.department and c.get("department", "").lower() != req.department.lower():
            match = False
        if match:
            results.append(c)
    resp = {"contacts": results, "total": len(results)}
    _log_call("contacts_search", req.model_dump(), resp)
    return resp


@app.post("/contacts/get")
def get_contact(req: GetRequest):
    for c in _contacts:
        if c.get("contact_id") == req.contact_id:
            resp = {"contact": c}
            _log_call("contacts_get", req.model_dump(), resp)
            return resp
    resp = {"error": f"Contact {req.contact_id} not found"}
    _log_call("contacts_get", req.model_dump(), resp)
    return JSONResponse(status_code=404, content=resp)


@app.get("/contacts/health")
def health():
    return {"status": "ok"}


@app.get("/contacts/audit")
def audit():
    return {"calls": _audit_log}


@app.post("/contacts/reset")
def reset():
    _load_fixtures()
    return {"status": "reset"}


import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _base import add_error_injection
add_error_injection(app)

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 9103))
    uvicorn.run(app, host="0.0.0.0", port=port)