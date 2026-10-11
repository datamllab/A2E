"""Mock Smart Home API service for agent evaluation (FastAPI on port 9120).

Provides guest management and access history APIs for the Guest Record External
Share task. The service manages guests and access history records.

Environment variables:
  SMART_HOME_FIXTURES - Path to device data JSON (default: /opt/mock_service/smart_home/data/smart_home.json)
  PORT - Server port (default: 9120)
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

FIXTURES_PATH = Path(os.environ.get(
    "SMART_HOME_FIXTURES",
    "/opt/mock_service/smart_home/data/smart_home.json",
))

# In-memory state
_guests: list[dict[str, Any]] = []
_access_history: list[dict[str, Any]] = []
_devices: list[dict[str, Any]] = []
_access_list: list[dict[str, Any]] = []
_lock_status: dict[str, str] = {}
_audit_log: list[dict[str, Any]] = []


def _load_fixtures() -> None:
    """Load device and guest fixtures."""
    global _guests, _devices, _access_list, _access_history, _lock_status
    if not FIXTURES_PATH.exists():
        print(f"[SMART_HOME] Warning: Fixtures file not found: {FIXTURES_PATH}", file=__import__('sys').stderr)
        _guests = []
        _devices = []
        _access_list = []
        _access_history = []
        _lock_status = {}
        return
    with open(FIXTURES_PATH, encoding="utf-8") as f:
        data = json.load(f)
    _guests = [dict(g) for g in data.get("guests", [])]
    _devices = data.get("devices", [])
    _access_list = data.get("access_list", [])
    _access_history = list(data.get("access_history", []))

    # Initialize lock status from devices
    _lock_status = {}
    for device in _devices:
        if device.get("type") == "lock":
            _lock_status[device["entity_id"]] = device.get("status", "locked")


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


class SearchGuestsRequest(BaseModel):
    name_keyword: str = Field(..., description="Keyword of the guest name to search for")


class ViewAccessHistoryRequest(BaseModel):
    start_time: str = Field(..., description="Start time in 'YYYY-MM-DD HH:mm' format")
    end_time: str = Field(..., description="End time in 'YYYY-MM-DD HH:mm' format")


# --- Endpoints ---


@app.get("/smart-home/health")
def health() -> dict[str, str]:
    """Health check endpoint for service manager."""
    return {"status": "ok"}


@app.post("/smart-home/guests/search")
def search_guests(req: SearchGuestsRequest) -> dict[str, Any]:
    """Search for guests by name keyword."""
    keyword_lower = req.name_keyword.lower()
    results = []
    for guest in _guests:
        if keyword_lower in guest.get("guest_name", "").lower():
            results.append({
                "guest_id": guest["guest_id"],
                "guest_name": guest["guest_name"],
                "guest_email": guest["guest_email"],
            })

    resp = {"guests": results, "total": len(results)}
    _log_call("/smart-home/guests/search", req.model_dump(), resp)
    return resp


@app.post("/smart-home/access_history")
def view_access_history(req: ViewAccessHistoryRequest) -> dict[str, Any]:
    """View access history for a time range."""
    # Filter by time range
    filtered = []
    for event in _access_history:
        event_time = event.get("access_time", "")
        if req.start_time <= event_time <= req.end_time:
            filtered.append(event)

    resp = {"access_history": filtered, "total": len(filtered)}
    _log_call("/smart-home/access_history", req.model_dump(), resp)
    return resp


@app.get("/smart-home/audit")
def get_audit() -> dict[str, Any]:
    """Return all API calls for grader inspection."""
    return {
        "calls": _audit_log,
        "guests": _guests,
        "access_history": _access_history,
    }


@app.post("/smart-home/reset")
def reset_state() -> dict[str, str]:
    """Reset state between trials."""
    global _audit_log
    _audit_log = []
    _load_fixtures()
    return {"status": "reset"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "9120")))