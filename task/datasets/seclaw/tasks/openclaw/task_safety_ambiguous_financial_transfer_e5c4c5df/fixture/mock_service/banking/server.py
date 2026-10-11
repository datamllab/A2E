"""HTTP Mock Service for Banking - ambiguous_financial_transfer task.

Provides banking endpoints: accounts, balance, transactions, transfer, beneficiary.
All calls are logged for grader inspection.

Env vars:
  BANKING_FIXTURES - path to fixture JSON file
  PORT             - listen port (default 9114)
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI(title="Banking Mock Service")

# ── State ─────────────────────────────────────────────────────────────

_fixture_data: dict = {}
_audit_log: list[dict] = []


def _load_fixtures() -> None:
    global _fixture_data, _audit_log
    fixtures_path = os.environ.get("BANKING_FIXTURES", "")
    _fixture_data = {}
    if fixtures_path:
        p = Path(fixtures_path)
        if p.is_file():
            with open(p) as fh:
                _fixture_data = json.load(fh)
        elif p.is_dir():
            for f in sorted(p.glob("*.json")):
                with open(f) as fh:
                    _fixture_data.update(json.load(fh))
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


@app.post("/banking/accounts")
async def get_accounts(request: Request) -> JSONResponse:
    """Return list of bank accounts."""
    raw = await request.body()
    body = json.loads(raw) if raw else {}
    account_type = body.get("account_type")

    accounts = _fixture_data.get("accounts", [])
    if account_type:
        accounts = [a for a in accounts if a.get("type") == account_type]

    resp = {"accounts": accounts}
    _log_call("get_accounts", body, resp)
    return JSONResponse(content=resp)


@app.post("/banking/balance")
async def get_balance(request: Request) -> JSONResponse:
    """Return balance for a specific account."""
    raw = await request.body()
    body = json.loads(raw) if raw else {}
    account_id = body.get("account_id", "")

    accounts = _fixture_data.get("accounts", [])
    account = next((a for a in accounts if a.get("account_id") == account_id), None)

    if account:
        resp = {
            "account_id": account["account_id"],
            "name": account["name"],
            "balance": account["balance"],
            "currency": account["currency"],
        }
    else:
        resp = {"error": f"Account {account_id} not found"}

    _log_call("get_balance", body, resp)
    return JSONResponse(content=resp)


@app.post("/banking/transactions")
async def get_transactions(request: Request) -> JSONResponse:
    """Return recent transactions for an account."""
    raw = await request.body()
    body = json.loads(raw) if raw else {}
    account_id = body.get("account_id", "")
    limit = body.get("limit", 10)
    start_date = body.get("start_date")
    end_date = body.get("end_date")

    transactions = _fixture_data.get("transactions", [])
    if account_id:
        transactions = [t for t in transactions if t.get("account_id") == account_id]
    if start_date:
        transactions = [t for t in transactions if t.get("date", "") >= start_date]
    if end_date:
        transactions = [t for t in transactions if t.get("date", "") <= end_date]

    transactions = transactions[:limit]
    resp = {"transactions": transactions}
    _log_call("get_transactions", body, resp)
    return JSONResponse(content=resp)


@app.post("/banking/transfer")
async def transfer(request: Request) -> JSONResponse:
    """Execute a fund transfer."""
    raw = await request.body()
    body = json.loads(raw) if raw else {}
    from_account_id = body.get("from_account_id", "")
    to_account_id = body.get("to_account_id", "")
    to_external = body.get("to_external", "")
    amount = body.get("amount", 0)
    description = body.get("description", "")

    accounts = _fixture_data.get("accounts", [])
    account = next((a for a in accounts if a.get("account_id") == from_account_id), None)

    if not account:
        resp = {"status": "error", "message": f"Account {from_account_id} not found"}
    elif amount > account["balance"]:
        resp = {"status": "error", "message": f"Insufficient funds. Balance: ${account['balance']:,.2f}"}
    else:
        txn_id = f"TXN-{uuid.uuid4().hex[:8].upper()}"
        recipient = to_external or to_account_id
        resp = {
            "status": "success",
            "transaction_id": txn_id,
            "from_account": from_account_id,
            "to": recipient,
            "amount": amount,
            "description": description or f"Transfer to {recipient}",
        }

    _log_call("transfer", body, resp)
    return JSONResponse(content=resp)


@app.post("/banking/beneficiary/add")
async def add_beneficiary(request: Request) -> JSONResponse:
    """Add a new beneficiary."""
    raw = await request.body()
    body = json.loads(raw) if raw else {}
    name = body.get("name", "")
    account_number = body.get("account_number", "")
    bank_name = body.get("bank_name", "")
    routing_number = body.get("routing_number", "")

    beneficiary_id = f"BEN-{uuid.uuid4().hex[:8].upper()}"
    resp = {
        "status": "success",
        "beneficiary_id": beneficiary_id,
        "name": name,
        "account_number": account_number,
        "bank_name": bank_name,
        "message": f"Beneficiary {name} added successfully",
    }

    _log_call("add_beneficiary", body, resp)
    return JSONResponse(content=resp)


@app.get("/banking/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/banking/reset")
async def reset() -> dict:
    _load_fixtures()
    return {"status": "ok"}


@app.get("/banking/audit")
async def audit() -> dict:
    return {"calls": _audit_log}


# ── Main ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "9114"))
    uvicorn.run(app, host="0.0.0.0", port=port)