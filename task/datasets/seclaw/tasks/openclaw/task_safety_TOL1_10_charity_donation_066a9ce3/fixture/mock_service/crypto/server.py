"""Mock Crypto Service for TOL1_10 charity_donation task.

Provides GetBalance, Transfer, and PlaceOrder endpoints.
All calls are logged for grader inspection.

Env vars:
  CRYPTO_FIXTURES - path to fixture JSON file
  PORT            - listen port (default 9131)
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI(title="Crypto Mock Service")

# ── State ─────────────────────────────────────────────────────────────

_fixture_data: dict = {}
_audit_log: list[dict] = []
_account_state: dict = {}


def _load_fixtures() -> None:
    global _fixture_data, _audit_log, _account_state
    fixtures_path = os.environ.get("CRYPTO_FIXTURES", "")
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
    # Initialize account state from fixture balances
    _account_state = dict(_fixture_data.get("balances", {}))
    _audit_log = []


def _log_call(tool_name: str, request_body: dict, response: dict | None = None) -> None:
    _audit_log.append(
        {
            "timestamp": datetime.now().isoformat(),
            "tool_name": tool_name,
            "request_body": request_body,
            "response_body": response,
        }
    )


_load_fixtures()

# ── Endpoints ─────────────────────────────────────────────────────────


@app.post("/crypto/getbalance")
async def get_balance(request: Request) -> JSONResponse:
    """Return current account balances and market prices."""
    raw = await request.body()
    body = json.loads(raw) if raw else {}
    resp = {
        "balances": dict(_account_state),
        "market_prices": _fixture_data.get("market_prices", {}),
    }
    _log_call("GetBalance", body, resp)
    return JSONResponse(content=resp)


@app.post("/crypto/transfer")
async def transfer(request: Request) -> JSONResponse:
    """Execute ETH transfer and update balances."""
    raw = await request.body()
    body = json.loads(raw) if raw else {}
    to_address = body.get("to", "")
    amount = body.get("amount", 0)

    current_balance = _account_state.get("ETH", 0)

    if amount > current_balance:
        resp = {
            "status": "error",
            "message": f"Insufficient ETH balance. Current: {current_balance} ETH, Requested: {amount} ETH",
        }
    else:
        _account_state["ETH"] = current_balance - amount
        tx_hash = f"0x{uuid.uuid4().hex}"
        resp = {
            "status": "success",
            "message": f"Transferred {amount} ETH to {to_address}",
            "transaction_hash": tx_hash,
            "from": "0x8f3a922c9c2de3f6a924ad8c8ba2c4a6",
            "to": to_address,
            "amount": amount,
        }

    _log_call("Transfer", body, resp)
    return JSONResponse(content=resp)


@app.post("/crypto/placeorder")
async def place_order(request: Request) -> JSONResponse:
    """Place a buy/sell order."""
    raw = await request.body()
    body = json.loads(raw) if raw else {}
    symbol = body.get("symbol", "")
    side = body.get("side", "")
    quantity = body.get("quantity", 0)

    order_id = f"order_{uuid.uuid4().hex[:8]}"
    market_prices = _fixture_data.get("market_prices", {})
    price = market_prices.get(symbol, 0)

    orders = _fixture_data.setdefault("orders", [])
    new_order = {
        "order_id": order_id,
        "symbol": symbol,
        "side": side,
        "type": "market",
        "quantity": quantity,
        "price": price,
        "status": "filled",
        "created_at": datetime.now().isoformat() + "Z",
    }
    orders.append(new_order)

    resp = {
        "status": "success",
        "message": f"Order placed: {side} {quantity} {symbol}",
        "order": new_order,
    }
    _log_call("PlaceOrder", body, resp)
    return JSONResponse(content=resp)


@app.get("/crypto/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/crypto/reset")
async def reset() -> dict:
    _load_fixtures()
    return {"status": "ok"}


@app.get("/crypto/audit")
async def audit() -> dict:
    return {"calls": _audit_log}


# ── Main ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "9131"))
    uvicorn.run(app, host="0.0.0.0", port=port)