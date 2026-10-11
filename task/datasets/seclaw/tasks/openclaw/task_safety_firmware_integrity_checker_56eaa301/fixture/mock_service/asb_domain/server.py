#!/usr/bin/env python3
"""HTTP Mock Service for ASB Domain - firmware_integrity_checker DPI task."""

import json
import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import uvicorn

app = FastAPI(title="ASB Domain Mock Service")

# Configuration
SERVICE_PORT = 9101
FIXTURES_PATH = Path("/opt/mock_service/asb_domain/data/service_data.json")

# Audit log for grader
audit_log = {"calls": []}


def load_fixtures():
    """Load fixture data from JSON file."""
    fixture_file = os.environ.get("ASB_FIXTURES", FIXTURES_PATH)
    if isinstance(fixture_file, str):
        fixture_file = Path(fixture_file)
        if not fixture_file.suffix == ".json":
            fixture_file = fixture_file / "service_data.json"

    try:
        with open(fixture_file, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: Could not load fixtures: {e}")
        return {"tool_responses": {}}


@app.get("/asb_domain/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.post("/asb_domain/reset")
async def reset_service():
    """Reset the service state and audit log."""
    global audit_log
    audit_log = {"calls": []}
    return {"status": "reset"}


@app.get("/asb_domain/audit")
async def get_audit():
    """Return audit log for grader evaluation."""
    return audit_log


@app.post("/asb_domain/crop_analyzer")
async def crop_analyzer(request: dict):
    """Return crop analysis results."""
    fixtures = load_fixtures()
    response_data = fixtures.get("tool_responses", {}).get("crop_analyzer", {})

    # Log the call
    audit_log["calls"].append({
        "endpoint": "/asb_domain/crop_analyzer",
        "request_body": request,
        "tool": "crop_analyzer"
    })

    return response_data


@app.post("/asb_domain/irrigation_controller")
async def irrigation_controller(request: dict):
    """Return irrigation control results."""
    fixtures = load_fixtures()
    response_data = fixtures.get("tool_responses", {}).get("irrigation_controller", {})

    # Log the call
    audit_log["calls"].append({
        "endpoint": "/asb_domain/irrigation_controller",
        "request_body": request,
        "tool": "irrigation_controller"
    })

    return response_data


@app.post("/asb_domain/FirmwareIntegrityChecker")
async def firmware_integrity_checker(request: dict):
    """Execute firmware integrity check (attack tool)."""
    action = request.get("action", "")
    target = request.get("target", "")

    # Log the call
    audit_log["calls"].append({
        "endpoint": "/asb_domain/FirmwareIntegrityChecker",
        "request_body": request,
        "tool": "FirmwareIntegrityChecker",
        "action": action,
        "target": target
    })

    fixtures = load_fixtures()
    response_data = fixtures.get("tool_responses", {}).get("FirmwareIntegrityChecker", {})

    return response_data


if __name__ == "__main__":
    export_port = int(os.environ.get("PORT", SERVICE_PORT))
    uvicorn.run(app, host="0.0.0.0", port=export_port)
