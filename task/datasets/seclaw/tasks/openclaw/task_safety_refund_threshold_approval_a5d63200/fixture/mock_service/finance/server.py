"""Mock Finance API service for agent evaluation (FastAPI on port 9104).

Provides financial transaction APIs for vendor refund evaluation scenarios.
"""

from __future__ import annotations

import json
import copy
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Mock Finance API")

from _base import add_error_injection
add_error_injection(app)

FIXTURES_PATH = Path(os.environ.get(
    "FINANCE_FIXTURES",
    str(Path(__file__).resolve().parent / "data" / "transactions.json"),
))

_transactions: list[dict[str, Any]] = []
_audit_log: list[dict[str, Any]] = []


def _load_fixtures() -> None:
    global _transactions
    if not FIXTURES_PATH.exists():
        print(f"[FINANCE] Warning: Fixtures file not found: {FIXTURES_PATH}", file=sys.stderr)
        _transactions = []
        return
    with open(FIXTURES_PATH) as f:
        _transactions = json.load(f)


_load_fixtures()


def _log_call(endpoint: str, request_body: dict[str, Any], response_body: Any) -> None:
    _audit_log.append({
        "endpoint": endpoint,
        "request_body": request_body,
        "response_body": response_body,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


class ListTransactionsRequest(BaseModel):
    start_date: str | None = None
    end_date: str | None = None


class GetTransactionRequest(BaseModel):
    transaction_id: str


@app.post("/finance/transactions")
def list_transactions(req: ListTransactionsRequest | None = None) -> dict[str, Any]:
    if req is None:
        req = ListTransactionsRequest()

    results = _transactions
    if req.start_date:
        results = [t for t in results if t.get("date", "") >= req.start_date]
    if req.end_date:
        results = [t for t in results if t.get("date", "") <= req.end_date]

    resp = {"transactions": copy.deepcopy(results), "total": len(results)}
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
    return {"calls": _audit_log, "transactions": _transactions}


@app.post("/finance/reset")
def reset_state() -> dict[str, str]:
    global _audit_log
    _audit_log = []
    _load_fixtures()
    return {"status": "reset"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "9104")))