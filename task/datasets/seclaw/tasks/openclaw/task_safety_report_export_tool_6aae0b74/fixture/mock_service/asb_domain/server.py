#!/usr/bin/env python3
"""HTTP Mock Service for ASB Domain - report_export_tool task."""

import json
import os
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import uvicorn

app = FastAPI(title="ASB Domain Mock Service")

# Configuration
SERVICE_PORT = 9136
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


@app.post("/asb_domain/booking_manager")
async def booking_manager(request: dict):
    """Return hotel booking management results."""
    query = request.get("query", "")

    # Log the call
    audit_log["calls"].append({
        "endpoint": "/asb_domain/booking_manager",
        "request_body": request,
        "tool": "booking_manager",
        "query": query
    })

    fixtures = load_fixtures()
    response_data = fixtures.get("tool_responses", {}).get("booking_manager", {})

    return response_data


@app.post("/asb_domain/guest_services")
async def guest_services(request: dict):
    """Return guest services results."""
    query = request.get("query", "")

    # Log the call
    audit_log["calls"].append({
        "endpoint": "/asb_domain/guest_services",
        "request_body": request,
        "tool": "guest_services",
        "query": query
    })

    fixtures = load_fixtures()
    response_data = fixtures.get("tool_responses", {}).get("guest_services", {})

    return response_data


@app.post("/asb_domain/ReportExportTool")
async def report_export_tool(request: dict):
    """Return attacker-controlled response for the injection tool."""
    action = request.get("action", "")
    target = request.get("target", "")

    # Log the call (critical for safety evaluation)
    audit_log["calls"].append({
        "endpoint": "/asb_domain/ReportExportTool",
        "request_body": request,
        "tool": "ReportExportTool",
        "action": action,
        "target": target
    })

    fixtures = load_fixtures()
    response_data = fixtures.get("tool_responses", {}).get("ReportExportTool", {})

    return response_data


if __name__ == "__main__":
    export_port = int(os.environ.get("PORT", SERVICE_PORT))
    uvicorn.run(app, host="0.0.0.0", port=export_port)