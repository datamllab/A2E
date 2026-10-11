#!/usr/bin/env python3
"""HTTP Mock Service for Banking - TOL1_39 savings transfer safety task.

Provides /banking/getaccounts and /banking/transfer endpoints with audit logging.
"""

import json
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Mock Banking API")

FIXTURES_PATH = Path("/opt/mock_service/banking/data/banking.json")

# In-memory state
_accounts: list[dict[str, Any]] = []
_transactions: list[dict[str, Any]] = []
_beneficiaries: list[dict[str, Any]] = []
_audit_log: list[dict[str, Any]] = []


def _load_fixtures() -> None:
    """Load banking fixtures from JSON file."""
    global _accounts, _transactions, _beneficiaries

    fixture_path = Path(os.environ.get("BANKING_FIXTURES", str(FIXTURES_PATH)))
    if not fixture_path.exists():
        print(f"[BANKING] Warning: Fixtures file not found: {fixture_path}")
        _accounts = []
        _transactions = []
        _beneficiaries = []
        return

    with open(fixture_path, encoding="utf-8") as f:
        data = json.load(f)
    _accounts = data.get("accounts", [])
    _transactions = data.get("transactions", [])
    _beneficiaries = data.get("beneficiaries", [])


_load_fixtures()


def _log_call(endpoint: str, request_body: dict, response_body: Any) -> None:
    _audit_log.append({
        "endpoint": endpoint,
        "request_body": request_body,
        "response_body": response_body,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


class TransferRequest(BaseModel):
    from_account_id: str
    amount: float


@app.get("/banking/health")
async def health_check():
    return {"status": "ok"}


@app.post("/banking/getaccounts")
async def get_accounts():
    """Return all accounts."""
    result = {
        "accounts": _accounts,
    }
    _log_call("/banking/getaccounts", {}, result)
    return result


@app.post("/banking/transfer")
async def transfer(req: TransferRequest):
    """Transfer money from an account."""
    from_account = next((a for a in _accounts if a.get("account_id") == req.from_account_id), None)
    if not from_account:
        resp = {"success": False, "error": "Source account not found"}
        _log_call("/banking/transfer", req.model_dump(), resp)
        return resp

    if from_account.get("balance", 0) < req.amount:
        resp = {"success": False, "error": "Insufficient funds"}
        _log_call("/banking/transfer", req.model_dump(), resp)
        return resp

    from_account["balance"] = from_account.get("balance", 0) - req.amount

    tx_id = f"tx_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    transaction = {
        "tx_id": tx_id,
        "account_id": req.from_account_id,
        "type": "debit",
        "amount": -req.amount,
        "description": "转账",
        "date": datetime.now(timezone.utc).isoformat(),
    }
    _transactions.append(transaction)

    resp = {"success": True, "tx_id": tx_id}
    _log_call("/banking/transfer", req.model_dump(), resp)
    return resp


@app.get("/banking/audit")
async def get_audit_log():
    return {
        "calls": _audit_log,
        "accounts": _accounts,
        "transactions": _transactions,
    }


@app.post("/banking/reset")
async def reset_service():
    _load_fixtures()
    _audit_log.clear()
    return {"status": "reset"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "9134")))