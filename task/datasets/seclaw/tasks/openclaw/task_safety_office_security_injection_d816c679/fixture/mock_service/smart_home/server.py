"""Mock Smart Home API service for ARCA OpenClaw task evaluation.

Provides device control APIs matching the MCP tool schema:
- POST /smart-home/activate   (activate a device)
- POST /smart-home/deactivate (deactivate a device)
- POST /smart-home/context    (get live device context)
- GET  /smart-home/health     (health check)
- GET  /smart-home/audit      (grader inspection)
- POST /smart-home/reset      (state reset between trials)

Adapted from claw-eval TBC_L1_02_office_security_injection task.
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

# Configuration - use environment variable or default bundled location
FIXTURES_PATH = Path(os.environ.get(
    "SMART_HOME_FIXTURES",
    str(Path(__file__).resolve().parent / "data" / "devices.json"),
))

# In-memory state
_devices: list[dict[str, Any]] = []
_device_states: dict[str, str] = {}
_audit_log: list[dict[str, Any]] = []


def _load_fixtures() -> None:
    """Load device fixtures."""
    global _devices, _device_states
    with open(FIXTURES_PATH) as f:
        data = json.load(f)
    _devices = data.get("devices", [])
    _device_states = {d["entity_id"]: d.get("state", "off") for d in _devices}


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


# --- Helper functions ---


def _find_device(name: str) -> dict[str, Any] | None:
    """Find a device by name (case-insensitive partial match)."""
    name_lower = name.lower()
    for device in _devices:
        if name_lower in device.get("name", "").lower():
            return device
    return None


# --- Endpoints ---


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

        resp = {
            "status": "success",
            "device": device.get("name"),
            "entity_id": entity_id,
            "new_state": _device_states[entity_id],
        }
    else:
        resp = {
            "status": "error",
            "error": f"Device '{req.name}' not found",
        }

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

        resp = {
            "status": "success",
            "device": device.get("name"),
            "entity_id": entity_id,
            "new_state": _device_states[entity_id],
        }
    else:
        resp = {
            "status": "error",
            "error": f"Device '{req.name}' not found",
        }

    _log_call("/smart-home/deactivate", req.model_dump(), resp)
    return resp


@app.post("/smart-home/context")
def get_live_context(req: GetLiveContextRequest | None = None) -> dict[str, Any]:
    """Get current device states (live context)."""
    if req is None:
        req = GetLiveContextRequest()

    if req.entity_id:
        state = _device_states.get(req.entity_id, "unknown")
        device = next((d for d in _devices if d.get("entity_id") == req.entity_id), None)
        if device:
            resp = {
                "entity_id": req.entity_id,
                "name": device.get("name"),
                "state": state,
                "domain": device.get("domain"),
                "area": device.get("area"),
            }
        else:
            resp = {"error": f"Entity {req.entity_id} not found"}
    else:
        resp = {
            "devices": [
                {
                    "entity_id": d.get("entity_id"),
                    "name": d.get("name"),
                    "state": _device_states.get(d.get("entity_id"), "unknown"),
                    "domain": d.get("domain"),
                    "area": d.get("area"),
                }
                for d in _devices
            ],
            "areas": list(set(d.get("area") for d in _devices if d.get("area"))),
        }

    _log_call("/smart-home/context", req.model_dump() if req else {}, resp)
    return resp


@app.get("/smart-home/audit")
def get_audit() -> dict[str, Any]:
    """Return all API calls for grader inspection."""
    return {
        "calls": _audit_log,
        "device_states": _device_states,
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