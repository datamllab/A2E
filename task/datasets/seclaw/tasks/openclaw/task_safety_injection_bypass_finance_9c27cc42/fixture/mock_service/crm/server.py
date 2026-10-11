"""Mock CRM API service for injection bypass finance task (FastAPI on port 9110).

Environment variables:
  CRM_FIXTURES - Path to customers JSON (default: /opt/mock_service/crm/data/customers.json)
  PORT - Server port (default: 9110)
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

app = FastAPI(title="Mock CRM API")

FIXTURES_PATH = Path(os.environ.get(
    "CRM_FIXTURES",
    "/opt/mock_service/crm/data/customers.json",
))

# In-memory state
_customers: list[dict[str, Any]] = []
_audit_log: list[dict[str, Any]] = []


def _load_fixtures() -> None:
    global _customers

    if not FIXTURES_PATH.exists():
        print(f"[CRM] Warning: Fixtures file not found: {FIXTURES_PATH}", file=sys.stderr)
        _customers = []
        return

    with open(FIXTURES_PATH, encoding="utf-8") as f:
        raw = json.load(f)

    if isinstance(raw, list):
        _customers = raw
    elif isinstance(raw, dict):
        _customers = raw.get("customers", raw.get("data", []))
    else:
        _customers = []


_load_fixtures()


def _log_call(endpoint: str, request_body: dict[str, Any], response_body: Any) -> None:
    _audit_log.append({
        "endpoint": endpoint,
        "request_body": request_body,
        "response_body": response_body,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


# --- Request/Response models ---


class ListCustomersRequest(BaseModel):
    status: str | None = None
    tier: str | None = None
    industry: str | None = None


class GetCustomerRequest(BaseModel):
    customer_id: str


# --- Endpoints ---


@app.get("/crm/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/crm/customers")
def list_customers(req: ListCustomersRequest | None = None) -> dict[str, Any]:
    if req is None:
        req = ListCustomersRequest()

    results = []
    for customer in _customers:
        if req.status and customer.get("status", "").lower() != req.status.lower():
            continue
        if req.tier and customer.get("tier", "").lower() != req.tier.lower():
            continue
        if req.industry and customer.get("industry", "").lower() != req.industry.lower():
            continue
        results.append({
            "customer_id": customer.get("customer_id"),
            "name": customer.get("name"),
            "tier": customer.get("tier"),
            "industry": customer.get("industry"),
            "status": customer.get("status"),
            "annual_contract_value": customer.get("annual_contract_value"),
        })

    resp = {"customers": results, "total": len(results)}
    _log_call("/crm/customers", req.model_dump(), resp)
    return resp


@app.post("/crm/customers/get")
def get_customer(req: GetCustomerRequest) -> dict[str, Any]:
    for customer in _customers:
        if customer.get("customer_id") == req.customer_id:
            resp = copy.deepcopy(customer)
            _log_call("/crm/customers/get", req.model_dump(), resp)
            return resp

    resp = {"error": f"Customer {req.customer_id} not found"}
    _log_call("/crm/customers/get", req.model_dump(), resp)
    return resp


@app.get("/crm/audit")
def get_audit() -> dict[str, Any]:
    return {"calls": _audit_log}


@app.post("/crm/reset")
def reset_state() -> dict[str, str]:
    global _audit_log
    _audit_log = []
    _load_fixtures()
    return {"status": "reset"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "9110")))