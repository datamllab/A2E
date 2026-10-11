#!/usr/bin/env python3
"""HTTP Mock Service for ASB Domain - drug_verification_tool task."""

import json
import os
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import uvicorn

app = FastAPI(title="ASB Domain Mock Service")

# Configuration
SERVICE_PORT = 9134
FIXTURES_PATH = Path("/opt/mock_service/asb_domain/data/service_data.json")

# Audit log for grader
audit_log = {"calls": []}

# Add error injection middleware
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _base import add_error_injection
add_error_injection(app)


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


@app.post("/asb_domain/veterinary_database")
async def veterinary_database(request: dict):
    """Return veterinary database query results."""
    query = request.get("query", "")

    # Log the call
    audit_log["calls"].append({
        "endpoint": "/asb_domain/veterinary_database",
        "request_body": request,
        "tool": "veterinary_database",
        "query": query
    })

    fixtures = load_fixtures()
    response_data = fixtures.get("tool_responses", {}).get("veterinary_database", {})

    return response_data


@app.post("/asb_domain/medication_manager")
async def medication_manager(request: dict):
    """Return medication manager results."""
    query = request.get("query", "")

    # Log the call
    audit_log["calls"].append({
        "endpoint": "/asb_domain/medication_manager",
        "request_body": request,
        "tool": "medication_manager",
        "query": query
    })

    fixtures = load_fixtures()
    response_data = fixtures.get("tool_responses", {}).get("medication_manager", {})

    return response_data


@app.post("/asb_domain/DrugVerificationTool")
async def drug_verification_tool(request: dict):
    """Return attacker-controlled response for the injection tool."""
    action = request.get("action", "")
    target = request.get("target", "")

    # Log the call (critical for safety evaluation)
    audit_log["calls"].append({
        "endpoint": "/asb_domain/DrugVerificationTool",
        "request_body": request,
        "tool": "DrugVerificationTool",
        "action": action,
        "target": target
    })

    fixtures = load_fixtures()
    response_data = fixtures.get("tool_responses", {}).get("DrugVerificationTool", {})

    return response_data


if __name__ == "__main__":
    export_port = int(os.environ.get("PORT", SERVICE_PORT))
    uvicorn.run(app, host="0.0.0.0", port=export_port)