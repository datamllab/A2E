#!/usr/bin/env python3
"""HTTP Mock Service for ASB Domain - pet_insurance_claims_tool task."""

import json
import os
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import uvicorn

app = FastAPI(title="ASB Domain Mock Service")

# Configuration
SERVICE_PORT = 9100
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


@app.get("/asb/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.post("/asb/reset")
async def reset_service():
    """Reset the service state and audit log."""
    global audit_log
    audit_log = {"calls": []}
    return {"status": "reset"}


@app.get("/asb/audit")
async def get_audit():
    """Return audit log for grader evaluation."""
    return audit_log


@app.post("/asb/tools/{tool_name}")
async def handle_tool(tool_name: str, request: dict = None):
    """Handle tool calls and return configured responses."""
    request = request or {}

    # Log the call
    audit_log["calls"].append({
        "endpoint": f"/asb/tools/{tool_name}",
        "request_body": request,
        "tool": tool_name
    })

    fixtures = load_fixtures()
    response_data = fixtures.get("tool_responses", {}).get(tool_name)

    if response_data is None:
        raise HTTPException(status_code=404, detail=f"Unknown tool: {tool_name}")

    return response_data


if __name__ == "__main__":
    export_port = int(os.environ.get("PORT", SERVICE_PORT))
    uvicorn.run(app, host="0.0.0.0", port=export_port)