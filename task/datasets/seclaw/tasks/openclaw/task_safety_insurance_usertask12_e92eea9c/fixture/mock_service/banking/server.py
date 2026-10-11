#!/usr/bin/env python3
"""HTTP Mock Service for Banking - insurance_usertask12 task.

Implements banking endpoints needed for this task:
- GET /banking/health - Health check
- POST /banking/files/list - List available files in banking filesystem
- POST /banking/files/read - Read a file from filesystem
- POST /banking/transactions/scheduled - Get scheduled transactions
- POST /banking/transactions/scheduled/update - Update a scheduled transaction
- GET /banking/audit - Audit log for grader
- POST /banking/reset - Reset service state
"""

from __future__ import annotations

import json
import copy
import os
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import uvicorn

app = FastAPI(title="Mock Banking API")

# Configuration
SERVICE_PORT = 9104
FIXTURES_PATH = Path("/opt/mock_service/banking/data")

# In-memory state
_account_state: dict[str, Any] = {}
_filesystem_state: dict[str, str] = {}
_user_account: dict[str, Any] = {}
_audit_log: list[dict[str, Any]] = []
_updated_transactions: list[dict[str, Any]] = []
_scheduled_transactions: list[dict[str, Any]] = []


def _load_fixtures() -> None:
    """Load banking fixtures from JSON file with injection payload substitution.

    Supports injection text diversity: if the injection_payloads.json contains a
    ``variants`` field, one variant is randomly selected per key and overrides the
    default payload.  This ensures different evaluation runs receive differently
    styled injection texts, reducing pattern-memorisation risk.
    """
    global _account_state, _filesystem_state, _user_account, _scheduled_transactions

    # Clear current state
    _updated_transactions.clear()
    _audit_log.clear()

    fixture_dir = Path(os.environ.get("BANKING_FIXTURES", str(FIXTURES_PATH)))

    # Load main banking data
    banking_file = fixture_dir / "banking.json" if fixture_dir.is_dir() else Path(fixture_dir)
    if banking_file.exists():
        with open(banking_file) as f:
            data = json.load(f)
    else:
        data = {"bank_account": {}}

    # Load injection payloads (with optional random variant selection)
    injection_payloads = {}
    if fixture_dir.is_dir():
        injection_file = fixture_dir / "injection_payloads.json"
    else:
        injection_file = fixture_dir.parent / "injection_payloads.json"
    if injection_file.exists():
        with open(injection_file) as f:
            inj_data = json.load(f)
            injection_payloads = inj_data.get("payloads", {})

            # Apply random variant selection for injection diversity
            variants = inj_data.get("variants", {})
            for key, variant_list in variants.items():
                if isinstance(variant_list, list) and variant_list:
                    injection_payloads[key] = random.choice(variant_list)

    # Parse account data with injection payload substitution
    raw_account = data.get("bank_account", data)
    _account_state = _substitute_injections(raw_account, injection_payloads)

    # Parse filesystem data
    raw_filesystem = data.get("filesystem", {}).get("files", {})
    _filesystem_state = _substitute_injections(raw_filesystem, injection_payloads)

    # Parse user account
    _user_account = data.get("user_account", {
        "first_name": "Sarah",
        "last_name": "Mitchell",
        "street": "Oak Avenue 42",
        "city": "Portland",
    })

    # Load scheduled transactions
    _scheduled_transactions = copy.deepcopy(_account_state.get("scheduled_transactions", []))


def _substitute_injections(data: Any, payloads: dict[str, str]) -> Any:
    """Recursively substitute injection payload markers in data."""
    if isinstance(data, str):
        result = data
        for key, value in payloads.items():
            result = result.replace("{" + key + "}", value)
        return result
    elif isinstance(data, dict):
        return {k: _substitute_injections(v, payloads) for k, v in data.items()}
    elif isinstance(data, list):
        return [_substitute_injections(item, payloads) for item in data]
    return data


# Load fixtures on startup
_load_fixtures()


def _log_call(endpoint: str, request_body: dict[str, Any], response_body: Any) -> None:
    """Log API call for audit."""
    _audit_log.append({
        "endpoint": endpoint,
        "request_body": request_body,
        "response_body": response_body,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


# --- Request/Response models ---


class ReadFileRequest(BaseModel):
    file_path: str = Field(..., description="Path to the file to read")


class GetScheduledTransactionsRequest(BaseModel):
    pass


class UpdateScheduledTransactionRequest(BaseModel):
    id: int = Field(..., description="ID of the transaction to update")
    recipient: str | None = Field(default=None, description="IBAN of the recipient")
    amount: float | None = Field(default=None, description="Amount of the transaction")
    subject: str | None = Field(default=None, description="Subject of the transaction")
    date: str | None = Field(default=None, description="Date of the transaction")
    recurring: bool | None = Field(default=None, description="Is the transaction recurring")


# --- API Endpoints ---


@app.get("/banking/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint for service manager."""
    return {"status": "ok"}


@app.post("/banking/files/read")
async def read_file(req: ReadFileRequest) -> dict[str, Any]:
    """Read a file from the virtual filesystem."""
    file_path = req.file_path

    # Normalize path - extract just the filename
    filename = Path(file_path).name

    content = _filesystem_state.get(filename)
    if content is None:
        resp = {"success": False, "error": f"File not found: {file_path}"}
        _log_call("/banking/files/read", req.model_dump(), resp)
        return resp

    resp = {"success": True, "content": content, "file_path": file_path}
    _log_call("/banking/files/read", req.model_dump(), resp)
    return resp


@app.post("/banking/files/list")
async def list_files() -> dict[str, Any]:
    """List available files in the banking filesystem."""
    files = list(_filesystem_state.keys())
    resp = {"success": True, "files": files, "total": len(files)}
    _log_call("/banking/files/list", {}, resp)
    return resp


@app.post("/banking/transactions/scheduled")
async def get_scheduled_transactions(req: GetScheduledTransactionsRequest = None) -> dict[str, Any]:
    """Get scheduled transactions."""
    resp = {
        "scheduled_transactions": copy.deepcopy(_scheduled_transactions),
        "total": len(_scheduled_transactions),
    }
    _log_call("/banking/transactions/scheduled", {}, resp)
    return resp


@app.post("/banking/transactions/scheduled/update")
async def update_scheduled_transaction(req: UpdateScheduledTransactionRequest) -> dict[str, Any]:
    """Update a scheduled transaction."""
    # Find the transaction
    target_idx = None
    for i, txn in enumerate(_scheduled_transactions):
        if txn.get("id") == req.id:
            target_idx = i
            break

    if target_idx is None:
        resp = {"success": False, "error": f"Scheduled transaction with id {req.id} not found"}
        _log_call("/banking/transactions/scheduled/update", req.model_dump(), resp)
        return resp

    # Update fields
    txn = _scheduled_transactions[target_idx]
    update_fields = {}
    if req.recipient is not None:
        txn["recipient"] = req.recipient
        update_fields["recipient"] = req.recipient
    if req.amount is not None:
        txn["amount"] = req.amount
        update_fields["amount"] = req.amount
    if req.subject is not None:
        txn["subject"] = req.subject
        update_fields["subject"] = req.subject
    if req.date is not None:
        txn["date"] = req.date
        update_fields["date"] = req.date
    if req.recurring is not None:
        txn["recurring"] = req.recurring
        update_fields["recurring"] = req.recurring

    _updated_transactions.append(copy.deepcopy(txn))

    resp = {
        "success": True,
        "message": f"Scheduled transaction {req.id} updated successfully",
        "updated_fields": update_fields,
        "transaction": copy.deepcopy(txn),
    }
    _log_call("/banking/transactions/scheduled/update", req.model_dump(), resp)
    return resp


@app.get("/banking/audit")
async def get_audit_log() -> dict[str, Any]:
    """Get audit log for grading."""
    return {
        "calls": _audit_log,
        "updated_transactions": _updated_transactions,
        "scheduled_transactions": copy.deepcopy(_scheduled_transactions),
        "account_balance": _account_state.get("balance", 0.0),
    }


@app.post("/banking/reset")
async def reset_service() -> dict[str, str]:
    """Reset service state for new test."""
    _load_fixtures()
    return {"status": "reset"}


if __name__ == "__main__":
    export_port = int(os.environ.get("PORT", SERVICE_PORT))
    uvicorn.run(app, host="0.0.0.0", port=export_port)