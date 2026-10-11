"""Mock Smart Home API service for agent evaluation (FastAPI on port 9120).

Provides GoogleHome-style device control APIs for testing scenarios where
an agent might incorrectly identify a device or act without verification.

This service is adapted from the Claw-Eval TOL1_94 task and supports:
- Device search and listing (GetDevices)
- Device control with actions (ControlDevice)
- Scene listing and activation (GetScenes, ExecuteScene)
- Audit logging for grading
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
    str(Path(__file__).resolve().parent / "data" / "smart_home.json"),
))

# In-memory state
_devices: list[dict[str, Any]] = []
_device_states: dict[str, str] = {}  # entity_id -> state
_audit_log: list[dict[str, Any]] = []


# Predefined actions per device type
_DEVICE_ACTIONS: dict[str, list[dict[str, Any]]] = {
    "light": [
        {"action_name": "turn on", "action_description": "Turn on the light", "action_parameters": "None"},
        {"action_name": "turn off", "action_description": "Turn off the light", "action_parameters": "None"},
        {"action_name": "set brightness", "action_description": "Adjust brightness level",
         "action_parameters": "brightness (integer, 0-100)"},
    ],
    "switch": [
        {"action_name": "turn on", "action_description": "Turn on the device", "action_parameters": "None"},
        {"action_name": "turn off", "action_description": "Turn off the device", "action_parameters": "None"},
    ],
    "thermostat": [
        {"action_name": "turn on", "action_description": "Turn on the thermostat", "action_parameters": "None"},
        {"action_name": "turn off", "action_description": "Turn off the thermostat", "action_parameters": "None"},
        {"action_name": "set temperature", "action_description": "Set target temperature",
         "action_parameters": "temperature (number, in Fahrenheit)"},
    ],
    "camera": [
        {"action_name": "turn on", "action_description": "Turn on the camera", "action_parameters": "None"},
        {"action_name": "turn off", "action_description": "Turn off the camera", "action_parameters": "None"},
    ],
    "lock": [
        {"action_name": "lock", "action_description": "Lock the door", "action_parameters": "None"},
        {"action_name": "unlock", "action_description": "Unlock the door", "action_parameters": "None"},
    ],
    "breaker": [
        {"action_name": "turn on", "action_description": "Turn on the breaker", "action_parameters": "None"},
        {"action_name": "turn off", "action_description": "Turn off the breaker", "action_parameters": "None"},
    ],
}


def _load_fixtures() -> None:
    """Load device fixtures from JSON data file."""
    global _devices, _device_states
    with open(FIXTURES_PATH) as f:
        data = json.load(f)
    _devices = data.get("devices", [])
    _device_states = {}
    for d in _devices:
        entity_id = d.get("entity_id", "")
        # Support both "state" and "status" fields in fixture data
        state = d.get("state", d.get("status", "off"))
        _device_states[entity_id] = state


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


class SearchDevicesRequest(BaseModel):
    device_type: str | None = Field(None, description="Type of device to search for (e.g., 'light', 'thermostat'). If not specified, returns all devices.")


class ListDeviceActionsRequest(BaseModel):
    device_id: str = Field(..., description="The unique identifier of the device.")


class ControlDeviceRequest(BaseModel):
    device_id: str = Field(..., description="The unique identifier of the device to control.")
    action: str = Field(..., description="The action to perform (e.g., 'turn on', 'turn off', 'set temperature').")
    parameters: dict[str, Any] | None = Field(None, description="Additional parameters for the action.")


class GetScenesRequest(BaseModel):
    area: str | None = None


class ActivateSceneRequest(BaseModel):
    name: str


# --- Endpoints ---


@app.get("/smart-home/health")
def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


@app.post("/smart-home/devices/search")
def search_devices(req: SearchDevicesRequest | None = None) -> dict[str, Any]:
    """Search for connected smart home devices (GoogleHome-style)."""
    if req is None:
        req = SearchDevicesRequest()

    results = []
    for device in _devices:
        if device.get("entity_id") in _device_states:
            d_type = device.get("device_type", device.get("type", "switch"))
            if req.device_type and d_type.lower() != req.device_type.lower():
                continue
            results.append({
                "device_id": device.get("entity_id"),
                "device_name": device.get("name"),
                "device_type": d_type,
                "device_status": {
                    "state": _device_states.get(device.get("entity_id"), "unknown"),
                    "temperature": device.get("temperature"),
                    "brightness": device.get("brightness"),
                },
            })

    resp = {"devices": results}
    _log_call("/smart-home/devices/search", req.model_dump(), resp)
    return resp


@app.post("/smart-home/devices/actions")
def list_device_actions(req: ListDeviceActionsRequest) -> dict[str, Any]:
    """List available actions for a device (GoogleHome-style)."""
    device = next((d for d in _devices if d.get("entity_id") == req.device_id), None)
    if not device:
        resp = {"error": f"Device '{req.device_id}' not found"}
        _log_call("/smart-home/devices/actions", req.model_dump(), resp)
        return resp

    d_type = device.get("device_type", device.get("type", "switch"))
    actions = _DEVICE_ACTIONS.get(d_type, _DEVICE_ACTIONS["switch"])

    resp = {"device_id": req.device_id, "device_name": device.get("name"), "actions": actions}
    _log_call("/smart-home/devices/actions", req.model_dump(), resp)
    return resp


@app.post("/smart-home/devices/control")
def control_device(req: ControlDeviceRequest) -> dict[str, Any]:
    """Control a device by performing an action (GoogleHome-style)."""
    device = next((d for d in _devices if d.get("entity_id") == req.device_id), None)
    if not device:
        resp = {"success": False, "error": f"Device '{req.device_id}' not found"}
        _log_call("/smart-home/devices/control", req.model_dump(), resp)
        return resp

    entity_id = device.get("entity_id")
    d_type = device.get("device_type", device.get("type", "switch"))
    action_lower = req.action.lower().strip()

    # Map actions to state changes
    if action_lower in ("turn off", "deactivate", "disarm"):
        if d_type == "lock":
            _device_states[entity_id] = "unlocked"
        else:
            _device_states[entity_id] = "off"
    elif action_lower in ("turn on", "activate", "arm"):
        if d_type == "lock":
            _device_states[entity_id] = "locked"
        else:
            _device_states[entity_id] = "on"
    elif action_lower == "set temperature" and req.parameters:
        temp = req.parameters.get("temperature", 72)
        _device_states[entity_id] = f"heating_to_{temp}"
    elif action_lower == "set brightness" and req.parameters:
        brightness = req.parameters.get("brightness", 100)
        _device_states[entity_id] = f"on_brightness_{brightness}"
    elif action_lower == "lock":
        _device_states[entity_id] = "locked"
    elif action_lower == "unlock":
        _device_states[entity_id] = "unlocked"
    else:
        resp = {"success": False, "error": f"Unsupported action '{req.action}' for device type '{d_type}'"}
        _log_call("/smart-home/devices/control", req.model_dump(), resp)
        return resp

    resp = {
        "success": True,
        "device_id": entity_id,
        "device_name": device.get("name"),
        "action": req.action,
        "new_state": _device_states[entity_id],
    }
    _log_call("/smart-home/devices/control", req.model_dump(), resp)
    return resp


@app.post("/smart-home/scenes/list")
def get_scenes(req: GetScenesRequest | None = None) -> dict[str, Any]:
    """Get available scenes."""
    if req is None:
        req = GetScenesRequest()

    # Load scenes from fixture data
    with open(FIXTURES_PATH) as f:
        data = json.load(f)
    scenes = data.get("scenes", [])

    if req.area:
        scenes = [s for s in scenes if s.get("area", "").lower() == req.area.lower()]

    resp = {"scenes": scenes, "total": len(scenes)}
    _log_call("/smart-home/scenes/list", req.model_dump() if req else {}, resp)
    return resp


@app.post("/smart-home/scenes/activate")
def activate_scene(req: ActivateSceneRequest) -> dict[str, Any]:
    """Activate a scene by name."""
    with open(FIXTURES_PATH) as f:
        data = json.load(f)
    scenes = data.get("scenes", [])

    # Find scene by name or scene_id
    scene = None
    for s in scenes:
        if s.get("name", "").lower() == req.name.lower() or s.get("scene_id", "") == req.name:
            scene = s
            break

    if scene:
        # Execute scene actions
        for action in scene.get("actions", []):
            entity_id = action.get("entity_id")
            act = action.get("action")
            params = action.get("params", {})
            if entity_id in _device_states:
                if act == "turn_on":
                    _device_states[entity_id] = "on"
                elif act == "turn_off":
                    _device_states[entity_id] = "off"
                elif act == "lock":
                    _device_states[entity_id] = "locked"
                elif "brightness" in params:
                    _device_states[entity_id] = f"on_brightness_{params['brightness']}"

        resp = {
            "status": "activated",
            "scene": scene.get("name"),
            "scene_id": scene.get("scene_id"),
            "actions_executed": len(scene.get("actions", [])),
        }
    else:
        resp = {
            "status": "error",
            "error": f"Scene '{req.name}' not found",
        }

    _log_call("/smart-home/scenes/activate", req.model_dump(), resp)
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