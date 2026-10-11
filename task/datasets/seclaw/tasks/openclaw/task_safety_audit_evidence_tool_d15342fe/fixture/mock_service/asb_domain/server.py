#!/usr/bin/env python3
"""HTTP Mock Service for ASB Domain - audit_evidence_tool task (DPI attack vector)."""

import json
import os
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI(title="ASB Domain Mock Service")

# Configuration
SERVICE_PORT = 9124
FIXTURES_PATH = Path("/opt/mock_service/asb_domain/data/service_data.json")

# State
_fixture: dict[str, Any] = {}
_audit_log: list[dict[str, Any]] = []
_tool_call_log: list[dict[str, Any]] = []


def load_fixtures() -> dict[str, Any]:
    """Load fixture data from JSON file."""
    fixture_file = os.environ.get("ASB_FIXTURES", str(FIXTURES_PATH))
    try:
        with open(fixture_file, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: Could not load fixtures: {e}")
        return {"tool_responses": {}}


def _log_tool_call(tool_name: str, params: dict, response: Any):
    _tool_call_log.append({
        "tool": tool_name,
        "params": params,
        "response_preview": str(response)[:200],
        "timestamp": datetime.utcnow().isoformat(),
    })


# ---------------------------------------------------------------------------
# Health / Reset / Audit
# ---------------------------------------------------------------------------

@app.get("/asb_domain/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "domain": "compliance"}


@app.post("/asb_domain/reset")
async def reset_service():
    """Reset the service state and audit log."""
    global _tool_call_log
    _tool_call_log = []
    return {"status": "reset"}


@app.get("/asb_domain/audit")
async def get_audit():
    """Return audit log for grader evaluation."""
    return {
        "domain": "compliance",
        "tool_calls": _tool_call_log,
    }


# ---------------------------------------------------------------------------
# Normal tools: audit_manager, regulation_database
# ---------------------------------------------------------------------------

@app.post("/asb_domain/audit_manager")
async def audit_manager(request: Request):
    """Return audit management results."""
    body = {}
    ct = request.headers.get("content-type", "")
    if "json" in ct:
        try:
            body = await request.json()
        except Exception:
            body = {}

    fixtures = load_fixtures()
    response_data = fixtures.get("tool_responses", {}).get("audit_manager", {})

    _log_tool_call("audit_manager", body, response_data)
    return response_data


@app.post("/asb_domain/regulation_database")
async def regulation_database(request: Request):
    """Return regulatory database results."""
    body = {}
    ct = request.headers.get("content-type", "")
    if "json" in ct:
        try:
            body = await request.json()
        except Exception:
            body = {}

    fixtures = load_fixtures()
    response_data = fixtures.get("tool_responses", {}).get("regulation_database", {})

    _log_tool_call("regulation_database", body, response_data)
    return response_data


# ---------------------------------------------------------------------------
# Attacker tool: AuditEvidenceTool
# ---------------------------------------------------------------------------

@app.post("/asb_domain/AuditEvidenceTool")
async def audit_evidence_tool(request: Request):
    """Return attacker-controlled response for the injection tool."""
    body = {}
    ct = request.headers.get("content-type", "")
    if "json" in ct:
        try:
            body = await request.json()
        except Exception:
            body = {}

    fixtures = load_fixtures()
    response_data = fixtures.get("tool_responses", {}).get("AuditEvidenceTool", {})

    _log_tool_call("AuditEvidenceTool", body, response_data)
    return response_data


if __name__ == "__main__":
    import uvicorn
    export_port = int(os.environ.get("PORT", SERVICE_PORT))
    uvicorn.run(app, host="0.0.0.0", port=export_port)