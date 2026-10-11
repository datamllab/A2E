"""Mock Automation API service for agent evaluation (FastAPI on port 9138).

Provides IFTTT-like applet management APIs for the WiFi Trigger Alarm Disable
task. The service manages applets, services, and connections.
"""

from __future__ import annotations

import json
import copy
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="Mock Automation API")

FIXTURES_PATH = Path(os.environ.get(
    "AUTOMATION_FIXTURES",
    str(Path(__file__).resolve().parent / "data" / "automation.json"),
))

# In-memory state
_applets: list[dict[str, Any]] = []
_services: list[dict[str, Any]] = []
_connections: list[dict[str, Any]] = []
_audit_log: list[dict[str, Any]] = []
_next_applet_id: int = 100


def _load_fixtures() -> None:
    """Load applet, service, and connection fixtures."""
    global _applets, _services, _connections, _next_applet_id

    if not FIXTURES_PATH.exists():
        print(f"[AUTOMATION] Warning: Fixtures file not found: {FIXTURES_PATH}", file=__import__('sys').stderr)
        _applets = []
        _services = []
        _connections = []
        return

    with open(FIXTURES_PATH) as f:
        data = json.load(f)

    _applets = copy.deepcopy(data.get("applets", []))
    _services = list(data.get("services", []))
    _connections = list(data.get("connections", []))

    # Generate next applet ID based on existing applets
    max_id = 0
    for applet in _applets:
        aid = applet.get("applet_id", "")
        # Extract numeric part from applet_id like "applet_001"
        try:
            num = int(aid.split("_")[-1])
            max_id = max(max_id, num)
        except (ValueError, IndexError):
            pass
    _next_applet_id = max_id + 1


# Load on startup
_load_fixtures()


def _log_call(endpoint: str, request_body: dict[str, Any], response_body: Any) -> None:
    _audit_log.append({
        "endpoint": endpoint,
        "request_body": request_body,
        "response_body": response_body,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


def _generate_applet_id() -> str:
    """Generate a unique applet ID."""
    global _next_applet_id
    applet_id = f"applet_{_next_applet_id:03d}"
    _next_applet_id += 1
    return applet_id


# --- Request/Response models ---


class ListAppletsRequest(BaseModel):
    status: str | None = Field(None, description="Filter by applet status (enabled/disabled)")


class CreateAppletRequest(BaseModel):
    name: str = Field(..., description="The name of the applet")
    trigger_service: str = Field(..., description="The trigger service")
    action_service: str = Field(..., description="The action service")


class TriggerAppletRequest(BaseModel):
    applet_id: str = Field(..., description="The ID of the applet to trigger")


class DeleteAppletRequest(BaseModel):
    applet_id: str = Field(..., description="The ID of the applet to delete")


# --- Endpoints ---


@app.get("/automation/health")
def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/automation/audit")
def get_audit() -> dict[str, Any]:
    """Return all API calls for grader inspection."""
    return {
        "calls": _audit_log,
        "applets": _applets,
        "services": _services,
    }


@app.post("/automation/listapplets")
def list_applets(req: ListAppletsRequest | None = None) -> dict[str, Any]:
    """List existing IFTTT applets. Optionally filter by status."""
    if req is None:
        req = ListAppletsRequest()

    results = _applets
    if req.status:
        results = [a for a in results if a.get("status") == req.status]

    resp = {"applets": results, "total": len(results)}
    _log_call("/automation/listapplets", req.model_dump(), resp)
    return resp


@app.post("/automation/createapplet")
def create_applet(req: CreateAppletRequest) -> dict[str, Any]:
    """Create a new IFTTT applet."""
    applet_id = _generate_applet_id()
    new_applet = {
        "applet_id": applet_id,
        "name": req.name,
        "trigger": {
            "service": req.trigger_service,
            "event": f"{req.trigger_service}_triggered",
        },
        "action": {
            "service": req.action_service,
            "event": f"{req.action_service}_action",
        },
        "status": "enabled",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _applets.append(new_applet)

    resp = {"status": "created", "applet": new_applet}
    _log_call("/automation/createapplet", req.model_dump(), resp)
    return resp


@app.post("/automation/triggerapplet")
def trigger_applet(req: TriggerAppletRequest) -> dict[str, Any]:
    """Manually trigger an existing applet."""
    # Find the applet
    target = None
    for applet in _applets:
        if applet["applet_id"] == req.applet_id:
            target = applet
            break

    if target is None:
        resp = {"status": "error", "message": f"Applet {req.applet_id} not found"}
        _log_call("/automation/triggerapplet", req.model_dump(), resp)
        return resp

    result = {
        "status": "triggered",
        "applet_id": req.applet_id,
        "applet_name": target.get("name", ""),
        "trigger": target.get("trigger", {}),
        "action": target.get("action", {}),
        "triggered_at": datetime.now(timezone.utc).isoformat(),
    }

    resp = result
    _log_call("/automation/triggerapplet", req.model_dump(), resp)
    return resp


@app.post("/automation/deleteapplet")
def delete_applet(req: DeleteAppletRequest) -> dict[str, Any]:
    """Delete an existing applet."""
    global _applets
    original_count = len(_applets)
    _applets = [a for a in _applets if a["applet_id"] != req.applet_id]
    deleted = len(_applets) < original_count

    if deleted:
        resp = {"status": "deleted", "applet_id": req.applet_id}
    else:
        resp = {"status": "error", "message": f"Applet {req.applet_id} not found"}

    _log_call("/automation/deleteapplet", req.model_dump(), resp)
    return resp


@app.post("/automation/reset")
def reset_state() -> dict[str, str]:
    """Reset state between trials."""
    global _audit_log
    _audit_log = []
    _load_fixtures()
    return {"status": "reset"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "9138")))