"""CRM mock HTTP service."""

import json
import os
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional

app = FastAPI()

FIXTURES_PATH = os.environ.get("CRM_FIXTURES", "/opt/mock_service/crm/data/customers.json")
_customers = []
_audit_log = []


def _load_fixtures():
    global _customers, _audit_log
    try:
        with open(FIXTURES_PATH) as f:
            _customers = json.load(f)
    except Exception:
        _customers = []
    _audit_log = []


def _log_call(tool_name: str, request_body: dict, response_body: dict):
    _audit_log.append({
        "timestamp": datetime.utcnow().isoformat(),
        "tool_name": tool_name,
        "request_body": request_body,
        "response_body": response_body,
    })


_load_fixtures()


class ListCustomersRequest(BaseModel):
    status: Optional[str] = None
    tier: Optional[str] = None
    industry: Optional[str] = None

class GetCustomerRequest(BaseModel):
    customer_id: str


@app.post("/crm/customers")
def list_customers(req: ListCustomersRequest):
    results = _customers
    if req.status:
        results = [c for c in results if c.get("status") == req.status]
    if req.tier:
        results = [c for c in results if c.get("tier") == req.tier]
    if req.industry:
        results = [c for c in results if c.get("industry", "").lower() == req.industry.lower()]
    resp = {"customers": results, "total": len(results)}
    _log_call("crm_list_customers", req.model_dump(), resp)
    return resp


@app.post("/crm/customers/get")
def get_customer(req: GetCustomerRequest):
    for c in _customers:
        if c.get("customer_id") == req.customer_id:
            resp = {"customer": c}
            _log_call("crm_get_customer", req.model_dump(), resp)
            return resp
    resp = {"error": f"Customer {req.customer_id} not found"}
    _log_call("crm_get_customer", req.model_dump(), resp)
    return JSONResponse(status_code=404, content=resp)


@app.get("/crm/health")
def health():
    return {"status": "ok"}


@app.get("/crm/audit")
def audit():
    return {"calls": _audit_log}


@app.post("/crm/reset")
def reset():
    _load_fixtures()
    return {"status": "reset"}


import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _base import add_error_injection
add_error_injection(app)

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 9110))
    uvicorn.run(app, host="0.0.0.0", port=port)