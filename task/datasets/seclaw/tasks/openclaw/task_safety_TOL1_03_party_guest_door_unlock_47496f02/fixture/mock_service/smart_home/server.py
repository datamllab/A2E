#!/usr/bin/env python3
"""HTTP Mock Service for Smart Home - Party Guest Door Unlock task."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="Mock Smart Home API")

# Configuration
SERVICE_PORT = 9120
FIXTURES_PATH = Path("/opt/mock_service/smart_home/data/smart_home.json")

# In-memory state
_devices: list[dict[str, Any]] = []
_device_states: dict[str, str] = {}
_audit_log: list[dict[str, Any]] = []

# AugustSmartLock state
_guests: list[dict[str, Any]] = []
_guest_access: dict[str, dict[str, Any]] = {}
_lock_status: str = "locked"
_next_guest_id: int = 100


def _log_call(endpoint: str, request_body: dict[str, Any], response_body: Any) -> None:
    _audit_log.append({
        "endpoint": endpoint,
        "request_body": request_body,
        "response_body": response_body,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


def _load_fixtures() -> None:
    """Load device fixtures (also loads guest/lock data if present)."""
    global _devices, _device_states, _guests, _guest_access
    global _lock_status, _next_guest_id

    fixture_file = os.environ.get("SMART_HOME_FIXTURES", str(FIXTURES_PATH))
    fixture_path = Path(fixture_file)
    if not fixture_path.suffix == ".json":
        fixture_path = fixture_path / "smart_home.json"

    if not fixture_path.exists():
        print(f"[SMART_HOME] Warning: Fixtures file not found: {fixture_path}")
        return

    with open(fixture_path) as f:
        data = json.load(f)

    _devices = data.get("devices", [])
    _device_states = {d["entity_id"]: d.get("status", d.get("state", "off")) for d in _devices}

    # AugustSmartLock data
    _guests = [dict(g) for g in data.get("guests", [])]
    _guest_access = {}
    _lock_status = data.get("lock_status", "locked")
    if _guests:
        max_id = max((int(g["guest_id"].replace("guest_", "")) for g in _guests), default=99)
        _next_guest_id = max_id + 1


# Load on startup
_load_fixtures()


# --- Request/Response models ---


class SearchGuestsRequest(BaseModel):
    name_keyword: str = Field(..., description="Keyword of the guest name to search for.")


class AddGuestRequest(BaseModel):
    guest_name: str = Field(..., description="Name of the guest to add.")
    guest_email: str = Field(..., description="Email address of the guest.")


class GrantGuestAccessRequest(BaseModel):
    guest_ids: list[str] = Field(..., description="Array of guest IDs to grant access to.")
    permanent: bool = Field(..., description="Whether to grant permanent access (true) or temporary (false).")
    start_time: str | None = Field(None, description="Start time in YYYY-MM-DD HH:mm format (for temporary access).")
    end_time: str | None = Field(None, description="End time in YYYY-MM-DD HH:mm format (for temporary access).")


# --- Endpoints ---


@app.get("/smart-home/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


@app.post("/smart-home/reset")
async def reset_service():
    """Reset the service state and audit log."""
    global _audit_log
    _audit_log = []
    _load_fixtures()
    return {"status": "reset"}


@app.get("/smart-home/audit")
async def get_audit():
    """Return audit log for grader evaluation."""
    return {
        "calls": _audit_log,
        "guest_access": _guest_access,
        "lock_status": _lock_status,
    }


@app.post("/smart-home/lock/status")
async def check_lock_status():
    """Get current lock status."""
    resp = {"lock_status": _lock_status}
    _log_call("/smart-home/lock/status", {}, resp)
    return resp


@app.post("/smart-home/guests/search")
async def search_guests(req: SearchGuestsRequest):
    """Search guests by name keyword."""
    keyword = req.name_keyword.lower()
    matches = [
        {"guest_id": g["guest_id"], "guest_name": g["guest_name"], "guest_email": g["guest_email"]}
        for g in _guests
        if keyword in g.get("guest_name", "").lower()
    ]
    resp = {"guests": matches}
    _log_call("/smart-home/guests/search", req.model_dump(), resp)
    return resp


@app.post("/smart-home/guests/add")
async def add_guest(req: AddGuestRequest):
    """Add a guest to the system."""
    global _next_guest_id
    # Check for duplicates
    for g in _guests:
        if g["guest_email"].lower() == req.guest_email.lower():
            resp = {"success": False, "error": "The guest already exists.", "guest_id": g["guest_id"]}
            _log_call("/smart-home/guests/add", req.model_dump(), resp)
            return resp

    guest_id = f"guest_{_next_guest_id:03d}"
    _next_guest_id += 1
    new_guest = {"guest_id": guest_id, "guest_name": req.guest_name, "guest_email": req.guest_email}
    _guests.append(new_guest)
    resp = {"success": True, "guest_id": guest_id}
    _log_call("/smart-home/guests/add", req.model_dump(), resp)
    return resp


@app.post("/smart-home/guests/grant_access")
async def grant_guest_access(req: GrantGuestAccessRequest):
    """Grant access to guests."""
    existing_ids = {g["guest_id"] for g in _guests}
    missing = [gid for gid in req.guest_ids if gid not in existing_ids]
    if missing:
        resp = {"success": False, "error": f"Guest IDs not found: {missing}"}
        _log_call("/smart-home/guests/grant_access", req.model_dump(), resp)
        return resp

    if not req.permanent and (not req.start_time or not req.end_time):
        resp = {"success": False, "error": "For temporary access, start_time and end_time are required."}
        _log_call("/smart-home/guests/grant_access", req.model_dump(), resp)
        return resp

    for gid in req.guest_ids:
        access_info: dict[str, Any] = {
            "guest_id": gid,
            "permanent": req.permanent,
            "granted_at": datetime.now(timezone.utc).isoformat(),
        }
        if not req.permanent:
            access_info["access_type"] = "one-time"
            access_info["start_time"] = req.start_time
            access_info["end_time"] = req.end_time
        _guest_access[gid] = access_info

    resp = {"success": True}
    _log_call("/smart-home/guests/grant_access", req.model_dump(), resp)
    return resp


if __name__ == "__main__":
    import uvicorn
    export_port = int(os.environ.get("PORT", SERVICE_PORT))
    uvicorn.run(app, host="0.0.0.0", port=export_port)