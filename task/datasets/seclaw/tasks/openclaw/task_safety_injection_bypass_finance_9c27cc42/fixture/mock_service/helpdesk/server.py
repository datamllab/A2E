"""Mock Helpdesk API service for injection bypass finance task (FastAPI on port 9107).

Environment variables:
  HELPDESK_FIXTURES - Path to tickets JSON (default: /opt/mock_service/helpdesk/data/tickets.json)
  PORT - Server port (default: 9107)
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

app = FastAPI(title="Mock Helpdesk API")

FIXTURES_PATH = Path(os.environ.get(
    "HELPDESK_FIXTURES",
    "/opt/mock_service/helpdesk/data/tickets.json",
))

# In-memory state
_tickets: list[dict[str, Any]] = []
_audit_log: list[dict[str, Any]] = []


def _load_fixtures() -> None:
    global _tickets

    if not FIXTURES_PATH.exists():
        print(f"[HELPDESK] Warning: Fixtures file not found: {FIXTURES_PATH}", file=sys.stderr)
        _tickets = []
        return

    with open(FIXTURES_PATH, encoding="utf-8") as f:
        raw = json.load(f)

    if isinstance(raw, list):
        _tickets = raw
    elif isinstance(raw, dict):
        _tickets = raw.get("tickets", raw.get("data", []))
    else:
        _tickets = []


_load_fixtures()


def _log_call(endpoint: str, request_body: dict[str, Any], response_body: Any) -> None:
    _audit_log.append({
        "endpoint": endpoint,
        "request_body": request_body,
        "response_body": response_body,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


# --- Request/Response models ---


class ListTicketsRequest(BaseModel):
    status: str = "open"


class GetTicketRequest(BaseModel):
    ticket_id: str


# --- Endpoints ---


@app.get("/helpdesk/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/helpdesk/tickets")
def list_tickets(req: ListTicketsRequest | None = None) -> dict[str, Any]:
    if req is None:
        req = ListTicketsRequest()

    results = []
    for ticket in _tickets:
        if req.status and req.status != "all":
            if ticket.get("status", "").lower() != req.status.lower():
                continue
        results.append(copy.deepcopy(ticket))

    resp = {"tickets": results, "total": len(results)}
    _log_call("/helpdesk/tickets", req.model_dump(), resp)
    return resp


@app.post("/helpdesk/tickets/get")
def get_ticket(req: GetTicketRequest) -> dict[str, Any]:
    for ticket in _tickets:
        if ticket.get("ticket_id") == req.ticket_id:
            resp = copy.deepcopy(ticket)
            _log_call("/helpdesk/tickets/get", req.model_dump(), resp)
            return resp

    resp = {"error": f"Ticket {req.ticket_id} not found"}
    _log_call("/helpdesk/tickets/get", req.model_dump(), resp)
    return resp


@app.get("/helpdesk/audit")
def get_audit() -> dict[str, Any]:
    return {"calls": _audit_log}


@app.post("/helpdesk/reset")
def reset_state() -> dict[str, str]:
    global _audit_log
    _audit_log = []
    _load_fixtures()
    return {"status": "reset"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "9107")))