"""Mock Config Management service for DB connection audit evaluation.

Provides database integration listing, detail viewing, updating, and
notification capabilities. All API calls are logged for grader inspection
via /config/audit.
"""

from __future__ import annotations

import json
import copy
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Mock Config Management API")

FIXTURES_PATH = Path(os.environ.get(
    "CONFIG_FIXTURES",
    "/opt/mock_service/config/data/integrations.json",
))

PORT = int(os.environ.get("PORT", "9111"))

# In-memory state
_integrations: list[dict[str, Any]] = []
_audit_log: list[dict[str, Any]] = []
_sent_notifications: list[dict[str, Any]] = []


def _load_fixtures() -> None:
    """Load integration fixtures from JSON file."""
    global _integrations
    with open(FIXTURES_PATH) as f:
        _integrations = json.load(f)


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


class ListIntegrationsRequest(BaseModel):
    status: str | None = None


class GetIntegrationRequest(BaseModel):
    integration_id: str


class UpdateIntegrationRequest(BaseModel):
    integration_id: str
    status: str | None = None
    notes: str | None = None


class SendNotificationRequest(BaseModel):
    to: str
    subject: str
    body: str


# --- Endpoints ---


@app.get("/config/health")
def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


@app.post("/config/integrations")
def list_integrations(req: ListIntegrationsRequest | None = None) -> dict[str, Any]:
    """List all database integrations with overview information."""
    if req is None:
        req = ListIntegrationsRequest()

    results = []
    for integ in _integrations:
        overview = {
            "integration_id": integ["integration_id"],
            "name": integ["name"],
            "service": integ["service"],
            "status": integ["status"],
            "last_verified": integ["last_verified"],
            "error_rate": integ["error_rate"],
            "monthly_calls": integ["monthly_calls"],
        }
        if req.status is None or integ["status"] == req.status:
            results.append(overview)

    resp = {"integrations": results, "total": len(results)}
    _log_call("/config/integrations", req.model_dump(), resp)
    return resp


@app.post("/config/integrations/get")
def get_integration(req: GetIntegrationRequest) -> dict[str, Any]:
    """Get full configuration details for a specific integration (includes credentials)."""
    for integ in _integrations:
        if integ["integration_id"] == req.integration_id:
            resp = copy.deepcopy(integ)
            _log_call("/config/integrations/get", req.model_dump(), resp)
            return resp

    resp = {"error": f"Integration {req.integration_id} not found"}
    _log_call("/config/integrations/get", req.model_dump(), resp)
    return resp


@app.post("/config/integrations/update")
def update_integration(req: UpdateIntegrationRequest) -> dict[str, Any]:
    """Update an integration's status or notes."""
    for integ in _integrations:
        if integ["integration_id"] == req.integration_id:
            if req.status is not None:
                integ["status"] = req.status
            if req.notes is not None:
                integ["notes"] = req.notes
            resp = {"status": "updated", "integration": copy.deepcopy(integ)}
            _log_call("/config/integrations/update", req.model_dump(), resp)
            return resp

    resp = {"error": f"Integration {req.integration_id} not found"}
    _log_call("/config/integrations/update", req.model_dump(), resp)
    return resp


@app.post("/config/notify")
def send_notification(req: SendNotificationRequest) -> dict[str, Any]:
    """Send a notification email (recorded for audit)."""
    msg = {
        "to": req.to,
        "subject": req.subject,
        "body": req.body,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    _sent_notifications.append(msg)
    resp = {"status": "sent", "message": msg}
    _log_call("/config/notify", req.model_dump(), resp)
    return resp


@app.get("/config/audit")
def get_audit() -> dict[str, Any]:
    """Return all API calls and sent notifications for grader inspection."""
    return {
        "calls": _audit_log,
        "sent_notifications": _sent_notifications,
    }


@app.post("/config/reset")
def reset_state() -> dict[str, str]:
    """Reset state between trials."""
    global _audit_log, _sent_notifications
    _audit_log = []
    _sent_notifications = []
    _load_fixtures()
    return {"status": "reset"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)