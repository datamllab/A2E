#!/usr/bin/env python3
"""HTTP Mock Service for ASB Domain - regulation_access_tool task (POT, Compliance).

This service implements a Prompt-Observable Task (POT): the injection is embedded
in the workspace SOUL.md file, not in tool responses. Normal tool responses return
clean data without injection payloads.
"""

import json
import os
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn

app = FastAPI(title="ASB Domain Mock Service")

# Configuration
SERVICE_PORT = 9104
FIXTURES_PATH = Path("/opt/mock_service/asb_domain/data/service_data.json")

# Audit log for grader
audit_log = {"calls": []}

# Fixture data
_fixture = {}


def load_fixtures():
    """Load fixture data from JSON file."""
    fixture_file = os.environ.get("ASB_FIXTURES", FIXTURES_PATH)
    if isinstance(fixture_file, str):
        fixture_file = Path(fixture_file)
        if fixture_file.is_dir():
            fixture_file = fixture_file / "service_data.json"

    try:
        with open(fixture_file, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: Could not load fixtures: {e}")
        return {"normal_tools": {}, "attacker_tools": {}, "injection_payloads": {}}


@app.on_event("startup")
def startup():
    global _fixture
    _fixture = load_fixtures()


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "domain": _fixture.get("domain", "unknown")}


@app.post("/reset")
async def reset_service():
    """Reset the service state and audit log."""
    global audit_log, _fixture
    audit_log = {"calls": []}
    _fixture = load_fixtures()
    return {"status": "reset"}


@app.get("/audit")
async def get_audit():
    """Return audit log for grader evaluation."""
    return audit_log


@app.post("/tools/{tool_name}")
async def call_tool(tool_name: str, request: Request):
    """Dynamic tool endpoint -- dispatches to normal or attacker tool responses.

    For normal tools: returns default response (no OPI injection for POT tasks)
    For attacker tools: returns attacker response
    """
    body = {}
    ct = request.headers.get("content-type", "")
    if "json" in ct:
        try:
            body = await request.json()
        except Exception:
            body = {}

    # Check normal tools
    normal = _fixture.get("normal_tools", {})
    if tool_name in normal:
        cfg = normal[tool_name]
        tpl = cfg.get("response_templates", {}).get("default", "")
        # Simple template substitution for request parameters
        response = tpl
        for k, v in body.items():
            response = response.replace("{" + k + "}", str(v))

        audit_log["calls"].append({
            "endpoint": f"/tools/{tool_name}",
            "tool": tool_name,
            "request_body": body,
            "response_preview": response[:200],
        })
        return {"result": response}

    # Check attacker tools
    attacker = _fixture.get("attacker_tools", {})
    if tool_name in attacker:
        cfg = attacker[tool_name]
        response = cfg.get("response", "")

        audit_log["calls"].append({
            "endpoint": f"/tools/{tool_name}",
            "tool": tool_name,
            "request_body": body,
            "response_preview": response[:200],
            "attacker_tool": True
        })
        return {"result": response}

    return JSONResponse(status_code=404, content={"error": f"Tool '{tool_name}' not found"})


if __name__ == "__main__":
    export_port = int(os.environ.get("PORT", SERVICE_PORT))
    uvicorn.run(app, host="0.0.0.0", port=export_port)