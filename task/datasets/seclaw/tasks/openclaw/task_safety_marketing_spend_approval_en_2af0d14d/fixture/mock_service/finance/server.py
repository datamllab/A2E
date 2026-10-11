"""Mock Finance API service for ARCA OpenClaw (FastAPI on port 9104)."""

from __future__ import annotations
import copy, json, os, sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
app = FastAPI(title="Mock Finance API")
from _base import add_error_injection
add_error_injection(app)

FIXTURES_PATH = Path(os.environ.get("FINANCE_FIXTURES", str(Path(__file__).resolve().parent / "data" / "transactions.json")))

_transactions: list[dict[str, Any]] = []
_audit_log: list[dict[str, Any]] = []

def _load_fixtures() -> None:
    global _transactions
    if not FIXTURES_PATH.exists():
        print(f"[FINANCE] Warning: Fixtures not found: {FIXTURES_PATH}", file=sys.stderr)
        _transactions = []
        return
    with open(FIXTURES_PATH) as f:
        _transactions = json.load(f)

_load_fixtures()

def _log_call(endpoint: str, request_body: dict[str, Any], response_body: Any) -> None:
    _audit_log.append({"endpoint": endpoint, "request_body": request_body, "response_body": response_body, "timestamp": datetime.now(timezone.utc).isoformat()})

class ListTransactionsRequest(BaseModel):
    start_date: str | None = None
    end_date: str | None = None
    customer_id: str | None = None
    transaction_type: str | None = None

class GetTransactionRequest(BaseModel):
    transaction_id: str

@app.post("/finance/transactions")
def list_transactions(req: ListTransactionsRequest | None = None) -> dict[str, Any]:
    if req is None:
        req = ListTransactionsRequest()
    results = []
    for t in _transactions:
        if req.start_date and t.get("date", "") < req.start_date:
            continue
        if req.end_date and t.get("date", "") > req.end_date:
            continue
        if req.customer_id and t.get("customer_id") != req.customer_id:
            continue
        if req.transaction_type and t.get("type") != req.transaction_type:
            continue
        results.append(copy.deepcopy(t))
    resp = {"transactions": results, "total": len(results)}
    _log_call("/finance/transactions", req.model_dump(), resp)
    return resp

@app.post("/finance/transactions/get")
def get_transaction(req: GetTransactionRequest) -> dict[str, Any]:
    for t in _transactions:
        if t["transaction_id"] == req.transaction_id:
            resp = copy.deepcopy(t)
            _log_call("/finance/transactions/get", req.model_dump(), resp)
            return resp
    resp = {"error": f"Transaction {req.transaction_id} not found"}
    _log_call("/finance/transactions/get", req.model_dump(), resp)
    return resp

@app.get("/finance/health")
async def finance_health():
    return {"status": "ok"}

@app.get("/finance/audit")
def get_audit() -> dict[str, Any]:
    return {"calls": _audit_log}

@app.post("/finance/reset")
def reset_state() -> dict[str, str]:
    global _audit_log
    _audit_log = []
    _load_fixtures()
    return {"status": "reset"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "9104")))
