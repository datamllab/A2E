"""Helpdesk mock HTTP service."""

import json
import os
from pathlib import Path
from datetime import datetime
from copy import deepcopy
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List

app = FastAPI()

FIXTURES_PATH = os.environ.get("HELPDESK_FIXTURES", "/opt/mock_service/helpdesk/data/tickets.json")
_tickets = []
_audit_log = []


def _load_fixtures():
    global _tickets, _audit_log
    try:
        with open(FIXTURES_PATH) as f:
            _tickets = json.load(f)
    except Exception:
        _tickets = []
    _audit_log = []


def _log_call(tool_name: str, request_body: dict, response_body: dict):
    _audit_log.append({
        "timestamp": datetime.utcnow().isoformat(),
        "tool_name": tool_name,
        "request_body": request_body,
        "response_body": response_body,
    })


_load_fixtures()


class ListTicketsRequest(BaseModel):
    status: str = "open"

class GetTicketRequest(BaseModel):
    ticket_id: str

class UpdateTicketRequest(BaseModel):
    ticket_id: str
    priority: Optional[str] = None
    tags: Optional[List[str]] = None
    category: Optional[str] = None


@app.post("/helpdesk/tickets")
def list_tickets(req: ListTicketsRequest):
    if req.status and req.status != "all":
        results = [t for t in _tickets if t.get("status") == req.status]
    else:
        results = _tickets
    resp = {"tickets": results, "total": len(results)}
    _log_call("helpdesk_list_tickets", req.model_dump(), resp)
    return resp


@app.post("/helpdesk/tickets/get")
def get_ticket(req: GetTicketRequest):
    for t in _tickets:
        if t.get("ticket_id") == req.ticket_id:
            resp = {"ticket": t}
            _log_call("helpdesk_get_ticket", req.model_dump(), resp)
            return resp
    resp = {"error": f"Ticket {req.ticket_id} not found"}
    _log_call("helpdesk_get_ticket", req.model_dump(), resp)
    return JSONResponse(status_code=404, content=resp)


@app.post("/helpdesk/tickets/update")
def update_ticket(req: UpdateTicketRequest):
    for t in _tickets:
        if t.get("ticket_id") == req.ticket_id:
            if req.priority is not None:
                t["priority"] = req.priority
            if req.tags is not None:
                t["tags"] = req.tags
            if req.category is not None:
                t["category"] = req.category
            t["updated_at"] = datetime.utcnow().isoformat()
            resp = {"ticket": t, "status": "updated"}
            _log_call("helpdesk_update_ticket", req.model_dump(), resp)
            return resp
    resp = {"error": f"Ticket {req.ticket_id} not found"}
    _log_call("helpdesk_update_ticket", req.model_dump(), resp)
    return JSONResponse(status_code=404, content=resp)


@app.get("/helpdesk/health")
def health():
    return {"status": "ok"}


@app.get("/helpdesk/audit")
def audit():
    return {"calls": _audit_log, "tickets": _tickets}


@app.post("/helpdesk/reset")
def reset():
    _load_fixtures()
    return {"status": "reset"}


import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _base import add_error_injection
add_error_injection(app)

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 9107))
    uvicorn.run(app, host="0.0.0.0", port=port)