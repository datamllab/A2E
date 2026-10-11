"""Finance mock HTTP service."""

import json
import os
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional

app = FastAPI()

FIXTURES_PATH = os.environ.get("FINANCE_FIXTURES", "/opt/mock_service/finance/data/transactions.json")
_transactions = []
_audit_log = []


def _load_fixtures():
    global _transactions, _audit_log
    try:
        with open(FIXTURES_PATH) as f:
            _transactions = json.load(f)
    except Exception:
        _transactions = []
    _audit_log = []


def _log_call(tool_name: str, request_body: dict, response_body: dict):
    _audit_log.append({
        "timestamp": datetime.utcnow().isoformat(),
        "tool_name": tool_name,
        "request_body": request_body,
        "response_body": response_body,
    })


_load_fixtures()


class ListTransactionsRequest(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None

class GetTransactionRequest(BaseModel):
    transaction_id: str


@app.post("/finance/transactions")
def list_transactions(req: ListTransactionsRequest):
    results = _transactions
    if req.start_date:
        results = [t for t in results if t.get("date", "") >= req.start_date]
    if req.end_date:
        results = [t for t in results if t.get("date", "") <= req.end_date]
    resp = {"transactions": results, "total": len(results)}
    _log_call("finance_list_transactions", req.model_dump(), resp)
    return resp


@app.post("/finance/transactions/get")
def get_transaction(req: GetTransactionRequest):
    for t in _transactions:
        if t.get("transaction_id") == req.transaction_id:
            resp = {"transaction": t}
            _log_call("finance_get_transaction", req.model_dump(), resp)
            return resp
    resp = {"error": f"Transaction {req.transaction_id} not found"}
    _log_call("finance_get_transaction", req.model_dump(), resp)
    return JSONResponse(status_code=404, content=resp)


@app.get("/finance/health")
def health():
    return {"status": "ok"}


@app.get("/finance/audit")
def audit():
    return {"calls": _audit_log}


@app.post("/finance/reset")
def reset():
    _load_fixtures()
    return {"status": "reset"}


import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _base import add_error_injection
add_error_injection(app)

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 9104))
    uvicorn.run(app, host="0.0.0.0", port=port)