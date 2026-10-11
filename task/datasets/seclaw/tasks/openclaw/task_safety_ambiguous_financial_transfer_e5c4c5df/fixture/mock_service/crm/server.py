"""HTTP Mock Service for CRM - ambiguous_financial_transfer task.

Provides CRM endpoints: list customers, get customer details.
All calls are logged for grader inspection.

Env vars:
  CRM_FIXTURES - path to fixture JSON file
  PORT          - listen port (default 9115)
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI(title="CRM Mock Service")

# ── State ─────────────────────────────────────────────────────────────

_fixture_data: list = []
_audit_log: list[dict] = []


def _load_fixtures() -> None:
    global _fixture_data, _audit_log
    fixtures_path = os.environ.get("CRM_FIXTURES", "")
    _fixture_data = []
    if fixtures_path:
        p = Path(fixtures_path)
        if p.is_file():
            with open(p) as fh:
                _fixture_data = json.load(fh)
        elif p.is_dir():
            for f in sorted(p.glob("*.json")):
                with open(f) as fh:
                    data = json.load(fh)
                    if isinstance(data, list):
                        _fixture_data.extend(data)
                    else:
                        _fixture_data.append(data)
    _audit_log = []


def _log_call(tool_name: str, request_body: dict, response: dict | None = None) -> None:
    _audit_log.append(
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tool_name": tool_name,
            "request_body": request_body,
            "response_body": response,
        }
    )


_load_fixtures()


# ── Endpoints ─────────────────────────────────────────────────────────


@app.post("/crm/customers")
async def list_customers(request: Request) -> JSONResponse:
    """Return list of customers/vendors, optionally filtered."""
    raw = await request.body()
    body = json.loads(raw) if raw else {}
    status = body.get("status")
    tier = body.get("tier")
    industry = body.get("industry")

    customers = list(_fixture_data)
    if status:
        customers = [c for c in customers if c.get("status") == status]
    if tier:
        customers = [c for c in customers if c.get("tier") == tier]
    if industry:
        customers = [c for c in customers if c.get("industry") == industry]

    resp = {"customers": customers}
    _log_call("list_customers", body, resp)
    return JSONResponse(content=resp)


@app.post("/crm/customers/get")
async def get_customer(request: Request) -> JSONResponse:
    """Return detailed information about a specific customer/vendor."""
    raw = await request.body()
    body = json.loads(raw) if raw else {}
    customer_id = body.get("customer_id", "")

    customer = next((c for c in _fixture_data if c.get("customer_id") == customer_id), None)

    if customer:
        resp = customer
    else:
        resp = {"error": f"Customer {customer_id} not found"}

    _log_call("get_customer", body, resp)
    return JSONResponse(content=resp)


@app.get("/crm/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/crm/reset")
async def reset() -> dict:
    _load_fixtures()
    return {"status": "ok"}


@app.get("/crm/audit")
async def audit() -> dict:
    return {"calls": _audit_log}


# ── Main ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "9115"))
    uvicorn.run(app, host="0.0.0.0", port=port)