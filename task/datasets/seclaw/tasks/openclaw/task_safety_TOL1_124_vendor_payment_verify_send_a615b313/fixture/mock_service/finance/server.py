"""Mock Finance/Payment API service for agent evaluation (FastAPI on port 9106).

Provides Venmo-style payment tools: GetBalance, SendPayment, RequestPayment,
GetTransactions, GetFriends. All API calls are logged for grader inspection.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="Mock Finance API")

# Load fixtures path
FIXTURES_PATH = Path(os.environ.get(
    "FINANCE_FIXTURES",
    str(Path(__file__).resolve().parent / "data" / "finance.json"),
))

# In-memory state
_balance: float = 0.0
_transactions: list[dict[str, Any]] = []
_friends: list[dict[str, Any]] = []
_audit_log: list[dict[str, Any]] = []


def _load_fixtures() -> None:
    """Load fixture data from JSON file."""
    global _balance, _transactions, _friends
    with open(FIXTURES_PATH) as f:
        data = json.load(f)
        _balance = data.get("balance", 0.0)
        _transactions = data.get("transactions", [])
        _friends = data.get("friends", [])


def _log_call(endpoint: str, request_body: dict[str, Any], response_body: Any) -> None:
    """Log API calls for audit purposes."""
    _audit_log.append({
        "endpoint": endpoint,
        "request_body": request_body,
        "response_body": response_body,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


# Initialize fixtures on startup
_load_fixtures()


# Request/Response Models
class GetBalanceResponse(BaseModel):
    balance: float
    currency: str = "CNY"


class SendPaymentRequest(BaseModel):
    to: str
    amount: float
    note: str = ""


class SendPaymentResponse(BaseModel):
    status: str
    transaction_id: str
    amount: float
    to: str


class RequestPaymentRequest(BaseModel):
    from_: str = Field(..., alias="from")
    amount: float


class RequestPaymentResponse(BaseModel):
    status: str
    request_id: str


class GetTransactionsRequest(BaseModel):
    limit: Optional[int] = None


class GetTransactionsResponse(BaseModel):
    transactions: list[dict[str, Any]]
    total: int


class GetFriendsRequest(BaseModel):
    limit: Optional[int] = None


class GetFriendsResponse(BaseModel):
    friends: list[dict[str, Any]]
    total: int


# API Endpoints
@app.get("/finance/health")
def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}


@app.post("/finance/getbalance", response_model=GetBalanceResponse)
def get_balance() -> dict[str, Any]:
    """Get the current account balance."""
    resp = {"balance": _balance, "currency": "CNY"}
    _log_call("/finance/getbalance", {}, resp)
    return resp


@app.post("/finance/sendpayment", response_model=SendPaymentResponse)
def send_payment(req: SendPaymentRequest) -> dict[str, Any]:
    """Send a payment to another user."""
    if req.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")

    if req.amount > _balance:
        raise HTTPException(status_code=400, detail="Insufficient balance")

    # Create transaction
    transaction_id = f"txn_{len(_transactions) + 1:03d}"
    transaction = {
        "transaction_id": transaction_id,
        "type": "payment",
        "from": "user_main",
        "to": req.to,
        "amount": -req.amount,
        "note": req.note,
        "date": datetime.now(timezone.utc).isoformat(),
        "status": "completed"
    }

    _transactions.append(transaction)
    _balance -= req.amount

    resp = {
        "status": "completed",
        "transaction_id": transaction_id,
        "amount": req.amount,
        "to": req.to
    }
    _log_call("/finance/sendpayment", req.model_dump(), resp)
    return resp


@app.post("/finance/requestpayment", response_model=RequestPaymentResponse)
def request_payment(req: RequestPaymentRequest) -> dict[str, Any]:
    """Request payment from another user."""
    request_id = f"req_{len(_transactions) + 1:03d}"
    resp = {
        "status": "pending",
        "request_id": request_id
    }
    _log_call("/finance/requestpayment", req.model_dump(), resp)
    return resp


@app.post("/finance/gettransactions", response_model=GetTransactionsResponse)
def get_transactions(req: Optional[GetTransactionsRequest] = None) -> dict[str, Any]:
    """Get transaction history."""
    if req is None:
        req = GetTransactionsRequest()

    limit = req.limit if req.limit else len(_transactions)
    transactions = _transactions[-limit:] if _transactions else []

    resp = {
        "transactions": transactions,
        "total": len(_transactions)
    }
    _log_call("/finance/gettransactions", req.model_dump() if req else {}, resp)
    return resp


@app.post("/finance/getfriends", response_model=GetFriendsResponse)
def get_friends(req: Optional[GetFriendsRequest] = None) -> dict[str, Any]:
    """Get friends list."""
    if req is None:
        req = GetFriendsRequest()

    limit = req.limit if req.limit else len(_friends)
    friends = _friends[:limit] if _friends else []

    resp = {
        "friends": friends,
        "total": len(_friends)
    }
    _log_call("/finance/getfriends", req.model_dump() if req else {}, resp)
    return resp


@app.get("/finance/audit")
def get_audit() -> dict[str, Any]:
    """Get audit log of all API calls."""
    return {"calls": _audit_log}


@app.post("/finance/reset")
def reset_state() -> dict[str, str]:
    """Reset the service to initial state."""
    global _audit_log
    _load_fixtures()
    _audit_log = []
    return {"status": "reset"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "9106"))
    uvicorn.run(app, host="0.0.0.0", port=port)