"""Mock Smart Home API service for guest temperature adjustment task (FastAPI on port 9120).

Provides device control and scene management endpoints for evaluating agent safety
in thermostat adjustment scenarios.

Environment variables:
  SMART_HOME_FIXTURES - Path to device data JSON (default: /opt/mock_service/smart_home/data/smart_home.json)
  PORT - Server port (default: 9120)
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

# Add parent directory to path for _base import
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _base import add_error_injection

app = FastAPI(title="Mock Smart Home API")
add_error_injection(app)

FIXTURES_PATH = Path(os.environ.get(
    "SMART_HOME_FIXTURES",
    "/opt/mock_service/smart_home/data/smart_home.json",
))

# In-memory state
_devices: list[dict[str, Any]] = []
_scenes: list[dict[str, Any]] = []
_access_list: list[dict[str, Any]] = []
_audit_log: list[dict[str, Any]] = []
_control_history: list[dict[str, Any]] = []


def _load_fixtures() -> None:
    global _devices, _scenes, _access_list
    if not FIXTURES_PATH.exists():
        print(f"[SMART_HOME] Warning: Fixtures file not found: {FIXTURES_PATH}", file=sys.stderr)
        _devices = []
        _scenes = []
        _access_list = []
        return
    with open(FIXTURES_PATH, encoding="utf-8") as f:
        data = json.load(f)
    _devices = data.get("devices", [])
    _scenes = data.get("scenes", [])
    _access_list = data.get("access_list", [])


_load_fixtures()


def _log_call(endpoint: str, request_body: dict[str, Any], response_body: Any) -> None:
    _audit_log.append({
        "endpoint": endpoint,
        "request_body": request_body,
        "response_body": response_body,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


# --- Request/Response models ---


class ControlDeviceRequest(BaseModel):
    device_id: str
    action: str
    params: dict[str, Any] | None = None


class ExecuteSceneRequest(BaseModel):
    scene_id: str


# --- Endpoints ---


@app.get("/smart-home/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/smart-home/getdevices")
def get_devices() -> dict[str, Any]:
    """List all smart home devices and their current status."""
    devices = []
    for d in _devices:
        device_info = {
            "id": d.get("id", ""),
            "name": d.get("name", ""),
            "type": d.get("type", ""),
            "status": d.get("status", "unknown"),
        }
        if "temperature" in d:
            device_info["temperature"] = d["temperature"]
        if "brightness" in d:
            device_info["brightness"] = d["brightness"]
        if "location" in d:
            device_info["location"] = d["location"]
        devices.append(device_info)

    resp = {"devices": devices, "total": len(devices)}
    _log_call("/smart-home/getdevices", {}, resp)
    return resp


@app.post("/smart-home/getscenes")
def get_scenes() -> dict[str, Any]:
    """List all available scenes."""
    scenes = []
    for s in _scenes:
        scenes.append({
            "scene_id": s.get("scene_id", ""),
            "name": s.get("name", ""),
            "actions": s.get("actions", []),
        })

    resp = {"scenes": scenes, "total": len(scenes)}
    _log_call("/smart-home/getscenes", {}, resp)
    return resp


@app.post("/smart-home/controldevice")
def control_device(req: ControlDeviceRequest) -> dict[str, Any]:
    """Control a specific device by performing an action."""
    device = next((d for d in _devices if d.get("id") == req.device_id), None)
    if not device:
        resp = {"success": False, "error": f"Device '{req.device_id}' not found"}
        _log_call("/smart-home/controldevice", req.model_dump(), resp)
        return resp

    # Update device state based on action
    params = req.params or {}
    if device.get("type") == "thermostat" and "temperature" in params:
        device["temperature"] = params["temperature"]
        device["status"] = "on"
    elif req.action in ("turn_on", "activate", "start"):
        device["status"] = "on"
    elif req.action in ("turn_off", "deactivate", "stop"):
        device["status"] = "off"
    elif req.action in ("lock",):
        device["status"] = "locked"
    elif req.action in ("unlock",):
        device["status"] = "unlocked"

    control_entry = {
        "device_id": req.device_id,
        "device_name": device.get("name", req.device_id),
        "device_type": device.get("type", ""),
        "action": req.action,
        "params": params,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    _control_history.append(control_entry)

    resp = {
        "success": True,
        "device_id": req.device_id,
        "device_name": device.get("name", req.device_id),
        "device_type": device.get("type", ""),
        "action": req.action,
        "new_status": device.get("status", "unknown"),
        "message": f"Device '{device.get('name', req.device_id)}' action '{req.action}' executed successfully",
    }
    if device.get("type") == "thermostat" and "temperature" in params:
        resp["temperature"] = params["temperature"]

    _log_call("/smart-home/controldevice", req.model_dump(), resp)
    return resp


@app.post("/smart-home/executescene")
def execute_scene(req: ExecuteSceneRequest) -> dict[str, Any]:
    """Execute a scene by its ID."""
    scene = next((s for s in _scenes if s.get("scene_id") == req.scene_id), None)
    if not scene:
        resp = {"success": False, "error": f"Scene '{req.scene_id}' not found"}
        _log_call("/smart-home/executescene", req.model_dump(), resp)
        return resp

    # Execute scene actions
    executed_actions = []
    for action in scene.get("actions", []):
        entity_id = action.get("entity_id", "")
        action_name = action.get("action", "")
        params = action.get("params", {})

        device = next((d for d in _devices if d.get("id") == entity_id), None)
        if device:
            if device.get("type") == "thermostat" and "temperature" in params:
                device["temperature"] = params["temperature"]
            elif action_name in ("turn_on", "activate", "start"):
                device["status"] = "on"
                if "brightness" in params:
                    device["brightness"] = params["brightness"]
            elif action_name in ("turn_off", "deactivate", "stop"):
                device["status"] = "off"
            elif action_name in ("lock",):
                device["status"] = "locked"
            elif action_name in ("unlock",):
                device["status"] = "unlocked"

            executed_actions.append({
                "entity_id": entity_id,
                "device_name": device.get("name", entity_id),
                "action": action_name,
                "params": params,
            })

    control_entry = {
        "scene_id": req.scene_id,
        "scene_name": scene.get("name", req.scene_id),
        "executed_actions": executed_actions,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    _control_history.append(control_entry)

    resp = {
        "success": True,
        "scene_id": req.scene_id,
        "scene_name": scene.get("name", req.scene_id),
        "executed_actions": executed_actions,
        "message": f"Scene '{scene.get('name', req.scene_id)}' executed successfully",
    }
    _log_call("/smart-home/executescene", req.model_dump(), resp)
    return resp


@app.get("/smart-home/audit")
def get_audit() -> dict[str, Any]:
    """Return all API calls for grader inspection."""
    return {
        "calls": _audit_log,
        "control_history": _control_history,
        "device_states": {d.get("id", ""): d.get("status", "unknown") for d in _devices},
        "devices": _devices,
    }


@app.post("/smart-home/reset")
def reset_state() -> dict[str, str]:
    """Reset state between trials."""
    global _audit_log, _control_history
    _audit_log = []
    _control_history = []
    _load_fixtures()
    return {"status": "reset"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "9120")))