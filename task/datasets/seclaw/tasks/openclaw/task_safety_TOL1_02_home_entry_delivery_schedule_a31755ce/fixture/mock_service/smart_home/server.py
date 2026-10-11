"""Mock Smart Home API service for agent evaluation (FastAPI on port 9120).

Provides device control and AugustSmartLock guest management APIs.
Adapted from claw-eval TOL1_02 for ARCA OpenClaw.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="Mock Smart Home API")

# Configuration
FIXTURES_PATH = Path(os.environ.get(
    "SMART_HOME_FIXTURES",
    str(Path(__file__).resolve().parent / "data" / "devices.json"),
))

# In-memory state
_devices: list[dict[str, Any]] = []
_device_states: dict[str, str] = {}  # entity_id -> state
_audit_log: list[dict[str, Any]] = []

# AugustSmartLock state
_guests: list[dict[str, Any]] = []
_guest_access: dict[str, dict[str, Any]] = {}  # guest_id -> access info
_access_codes: dict[str, dict[str, Any]] = {}  # code -> access info
_access_history: list[dict[str, Any]] = []
_lock_status: str = "locked"
_next_guest_id: int = 100


def _load_fixtures() -> None:
    """Load device fixtures (also loads guest/lock data if present)."""
    global _devices, _device_states, _guests, _guest_access, _access_codes
    global _access_history, _lock_status, _next_guest_id
    with open(FIXTURES_PATH) as f:
        data = json.load(f)
    _devices = data.get("devices", [])
    _device_states = {d["entity_id"]: d.get("status", d.get("state", "off")) for d in _devices}

    # AugustSmartLock data (optional, loaded if present)
    _guests = [dict(g) for g in data.get("guests", [])]
    _guest_access = {}
    for acc in data.get("guest_access", []):
        _guest_access[acc["guest_id"]] = dict(acc)
    _access_codes = {}
    _access_history = list(data.get("access_history", []))
    _lock_status = data.get("lock_status", "locked")
    if _guests:
        max_id = max((int(g["guest_id"].replace("guest_", "")) for g in _guests), default=99)
        _next_guest_id = max_id + 1


# Load on startup
_load_fixtures()


def _log_call(endpoint: str, request_body: dict[str, Any], response_body: Any) -> None:
    _audit_log.append({
        "endpoint": endpoint,
        "request_body": request_body,
        "response_body": response_body,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


# --- Request/Response models ---


class ActivateDeviceRequest(BaseModel):
    name: str = Field(..., description="Name of the device")
    domain: str | None = Field(None, description="Device domain")
    area: str | None = Field(None, description="Area name")


class DeactivateDeviceRequest(BaseModel):
    name: str = Field(..., description="Name of the device")
    domain: str | None = Field(None, description="Device domain")
    area: str | None = Field(None, description="Area name")


class GetLiveContextRequest(BaseModel):
    entity_id: str | None = Field(None, description="Optional specific entity ID to query")


class SearchGuestsRequest(BaseModel):
    name_keyword: str = Field(..., description="Keyword of the guest name to search for.")


class AddGuestRequest(BaseModel):
    guest_name: str = Field(..., description="Name of the guest to add.")
    guest_email: str = Field(..., description="Email address of the guest.")


class DeleteGuestRequest(BaseModel):
    guest_ids: list[str] = Field(..., description="Array of guest IDs to delete.")


class GrantGuestAccessRequest(BaseModel):
    guest_ids: list[str] = Field(..., description="Array of guest IDs to grant access to.")
    permanent: bool = Field(..., description="Whether to grant permanent access.")
    start_time: str | None = Field(None, description="Start time in YYYY-MM-DD HH:mm format.")
    end_time: str | None = Field(None, description="End time in YYYY-MM-DD HH:mm format.")


class RevokeGuestAccessRequest(BaseModel):
    guest_ids: list[str] = Field(..., description="Array of guest IDs to revoke access for.")


class GenerateAccessCodeRequest(BaseModel):
    start_time: str = Field(..., description="Start time in YYYY-MM-DD HH:mm format.")
    end_time: str = Field(..., description="End time in YYYY-MM-DD HH:mm format.")


class RevokeAccessCodeRequest(BaseModel):
    access_code: str = Field(..., description="The access code to revoke.")


class ViewAccessHistoryRequest(BaseModel):
    start_time: str = Field(..., description="Start time in YYYY-MM-DD HH:mm format.")
    end_time: str = Field(..., description="End time in YYYY-MM-DD HH:mm format.")


# --- Helper functions ---


def _find_device(name: str) -> dict[str, Any] | None:
    """Find a device by name (case-insensitive partial match)."""
    name_lower = name.lower()
    for device in _devices:
        if name_lower in device.get("name", "").lower():
            return device
    return None


# --- Device endpoints ---


@app.get("/smart-home/health")
def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


@app.post("/smart-home/activate")
def activate_device(req: ActivateDeviceRequest) -> dict[str, Any]:
    """Activate a device (turn on, open, lock, etc.)."""
    device = _find_device(req.name)

    if device:
        entity_id = device.get("entity_id")
        domain = device.get("domain")
        if domain == "cover":
            _device_states[entity_id] = "open"
        elif domain == "light":
            _device_states[entity_id] = "on"
        elif domain == "lock":
            _device_states[entity_id] = "locked"
        else:
            _device_states[entity_id] = "on"

        resp = {"status": "success", "device": device.get("name"), "entity_id": entity_id, "new_state": _device_states[entity_id]}
    else:
        resp = {"status": "error", "error": f"Device '{req.name}' not found"}

    _log_call("/smart-home/activate", req.model_dump(), resp)
    return resp


@app.post("/smart-home/deactivate")
def deactivate_device(req: DeactivateDeviceRequest) -> dict[str, Any]:
    """Deactivate a device (turn off, close, unlock, etc.)."""
    device = _find_device(req.name)

    if device:
        entity_id = device.get("entity_id")
        domain = device.get("domain")
        if domain == "cover":
            _device_states[entity_id] = "closed"
        elif domain == "light":
            _device_states[entity_id] = "off"
        elif domain == "lock":
            _device_states[entity_id] = "unlocked"
        else:
            _device_states[entity_id] = "off"

        resp = {"status": "success", "device": device.get("name"), "entity_id": entity_id, "new_state": _device_states[entity_id]}
    else:
        resp = {"status": "error", "error": f"Device '{req.name}' not found"}

    _log_call("/smart-home/deactivate", req.model_dump(), resp)
    return resp


@app.post("/smart-home/context")
def get_live_context(req: GetLiveContextRequest | None = None) -> dict[str, Any]:
    """Get current device states."""
    if req is None:
        req = GetLiveContextRequest()

    if req.entity_id:
        state = _device_states.get(req.entity_id, "unknown")
        device = next((d for d in _devices if d.get("entity_id") == req.entity_id), None)
        if device:
            resp = {"entity_id": req.entity_id, "name": device.get("name"), "state": state, "domain": device.get("domain"), "area": device.get("area")}
        else:
            resp = {"error": f"Entity {req.entity_id} not found"}
    else:
        resp = {
            "devices": [
                {"entity_id": d.get("entity_id"), "name": d.get("name"), "state": _device_states.get(d.get("entity_id"), "unknown"), "domain": d.get("domain"), "area": d.get("area")}
                for d in _devices
            ],
            "areas": list(set(d.get("area") for d in _devices if d.get("area"))),
        }

    _log_call("/smart-home/context", req.model_dump() if req else {}, resp)
    return resp


# --- AugustSmartLock endpoints ---


@app.post("/smart-home/lock/status")
def check_lock_status() -> dict[str, Any]:
    """Get current lock status."""
    resp = {"lock_status": _lock_status}
    _log_call("/smart-home/lock/status", {}, resp)
    return resp


@app.post("/smart-home/lock/lock")
def lock_door() -> dict[str, Any]:
    """Lock the door."""
    global _lock_status
    if _lock_status == "locked":
        resp = {"success": False, "error": "The door is already locked."}
    else:
        _lock_status = "locked"
        resp = {"success": True}
    _log_call("/smart-home/lock/lock", {}, resp)
    return resp


@app.post("/smart-home/lock/unlock")
def unlock_door() -> dict[str, Any]:
    """Unlock the door."""
    global _lock_status
    if _lock_status == "unlocked":
        resp = {"success": False, "error": "The door is already unlocked."}
    else:
        _lock_status = "unlocked"
        resp = {"success": True}
    _log_call("/smart-home/lock/unlock", {}, resp)
    return resp


@app.post("/smart-home/guests/search")
def search_guests(req: SearchGuestsRequest) -> dict[str, Any]:
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
def add_guest(req: AddGuestRequest) -> dict[str, Any]:
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


@app.post("/smart-home/guests/delete")
def delete_guests(req: DeleteGuestRequest) -> dict[str, Any]:
    """Delete guests from the system."""
    global _guests
    existing_ids = {g["guest_id"] for g in _guests}
    missing = [gid for gid in req.guest_ids if gid not in existing_ids]
    if missing:
        resp = {"success": False, "error": f"Guest IDs not found: {missing}"}
    else:
        _guests = [g for g in _guests if g["guest_id"] not in set(req.guest_ids)]
        for gid in req.guest_ids:
            _guest_access.pop(gid, None)
        resp = {"success": True}
    _log_call("/smart-home/guests/delete", req.model_dump(), resp)
    return resp


@app.post("/smart-home/guests/grant_access")
def grant_guest_access(req: GrantGuestAccessRequest) -> dict[str, Any]:
    """Grant access to guests."""
    existing_ids = {g["guest_id"] for g in _guests}
    missing = [gid for gid in req.guest_ids if gid not in existing_ids]
    if missing:
        resp = {"success": False, "error": f"Guest IDs not found: {missing}"}
        _log_call("/smart-home/guests/grant_access", req.model_dump(), resp)
        return resp

    if not req.permanent and (not req.start_time or not req.end_time):
        resp = {"success": False, "error": "start_time and end_time are required for temporary access."}
        _log_call("/smart-home/guests/grant_access", req.model_dump(), resp)
        return resp

    for gid in req.guest_ids:
        access_info: dict[str, Any] = {
            "guest_id": gid,
            "permanent": req.permanent,
            "granted_at": datetime.now(timezone.utc).isoformat(),
        }
        if not req.permanent:
            access_info["start_time"] = req.start_time
            access_info["end_time"] = req.end_time
        _guest_access[gid] = access_info

    resp = {"success": True}
    _log_call("/smart-home/guests/grant_access", req.model_dump(), resp)
    return resp


@app.post("/smart-home/guests/revoke_access")
def revoke_guest_access(req: RevokeGuestAccessRequest) -> dict[str, Any]:
    """Revoke access for guests."""
    existing_ids = {g["guest_id"] for g in _guests}
    missing = [gid for gid in req.guest_ids if gid not in existing_ids]
    if missing:
        resp = {"success": False, "error": f"Guest IDs not found: {missing}"}
    else:
        not_granted = [gid for gid in req.guest_ids if gid not in _guest_access]
        if not_granted:
            resp = {"success": False, "error": f"Access not granted for: {not_granted}"}
        else:
            for gid in req.guest_ids:
                _guest_access.pop(gid, None)
            resp = {"success": True}
    _log_call("/smart-home/guests/revoke_access", req.model_dump(), resp)
    return resp


@app.post("/smart-home/access_code/generate")
def generate_access_code(req: GenerateAccessCodeRequest) -> dict[str, Any]:
    """Generate a temporary access code."""
    import random
    import string
    code = "".join(random.choices(string.digits, k=6))
    _access_codes[code] = {
        "code": code,
        "start_time": req.start_time,
        "end_time": req.end_time,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    resp = {"access_code": code}
    _log_call("/smart-home/access_code/generate", req.model_dump(), resp)
    return resp


@app.post("/smart-home/access_code/revoke")
def revoke_access_code(req: RevokeAccessCodeRequest) -> dict[str, Any]:
    """Revoke a temporary access code."""
    if req.access_code not in _access_codes:
        resp = {"success": False, "error": "The access code does not exist."}
    else:
        _access_codes.pop(req.access_code)
        resp = {"success": True}
    _log_call("/smart-home/access_code/revoke", req.model_dump(), resp)
    return resp


@app.post("/smart-home/access_history")
def view_access_history(req: ViewAccessHistoryRequest) -> dict[str, Any]:
    """View access history for a time range."""
    filtered = []
    for event in _access_history:
        event_time = event.get("access_time", "")
        if req.start_time <= event_time <= req.end_time:
            filtered.append(event)
    resp = {"access_history": filtered}
    _log_call("/smart-home/access_history", req.model_dump(), resp)
    return resp


@app.get("/smart-home/audit")
def get_audit() -> dict[str, Any]:
    """Return all API calls for grader inspection."""
    return {
        "calls": _audit_log,
        "device_states": _device_states,
        "guest_access": _guest_access,
        "lock_status": _lock_status,
    }


@app.post("/smart-home/reset")
def reset_state() -> dict[str, str]:
    """Reset state between trials."""
    global _audit_log
    _audit_log = []
    _load_fixtures()  # Reset all state
    return {"status": "reset"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "9120")))