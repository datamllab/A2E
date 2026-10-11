#!/usr/bin/env python3
"""HTTP Mock Service for Agriculture Domain - DPI field_gps_validator task.

Provides crop_analyzer, irrigation_controller (normal tools) and
FieldGPSValidator (attacker tool) endpoints.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn

app = FastAPI(title="Agriculture Domain Mock Service")

SERVICE_PORT = 9110
FIXTURES_PATH = Path("/opt/mock_service/agriculture/data/agriculture.json")

audit_log: list[dict[str, Any]] = []

# Loaded fixtures
_fixture: dict[str, Any] = {}


def load_fixtures():
    fixture_file = os.environ.get("AGRICULTURE_FIXTURES", FIXTURES_PATH)
    if isinstance(fixture_file, str):
        fixture_file = Path(fixture_file)
        if fixture_file.is_dir():
            fixture_file = fixture_file / "agriculture.json"
    try:
        with open(fixture_file, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: Could not load fixtures: {e}")
        return {}


def _fill_template(template: str, params: dict) -> str:
    """Simple {key} substitution in response templates."""
    result = template
    for k, v in params.items():
        result = result.replace("{" + k + "}", str(v))
    return result


# ---------------------------------------------------------------------------
# Health / Reset / Audit
# ---------------------------------------------------------------------------

@app.get("/agriculture/health")
async def health_check():
    return {"status": "healthy", "domain": _fixture.get("domain", "agriculture_automation")}


@app.post("/agriculture/reset")
async def reset_service():
    global audit_log, _fixture
    audit_log = []
    _fixture = load_fixtures()
    return {"status": "reset"}


@app.get("/agriculture/audit")
async def get_audit():
    return {"domain": _fixture.get("domain", "agriculture_automation"), "calls": audit_log}


# ---------------------------------------------------------------------------
# Tool endpoints
# ---------------------------------------------------------------------------

@app.post("/agriculture/tools/{tool_name}")
async def call_tool(tool_name: str, request: Request):
    body = {}
    ct = request.headers.get("content-type", "")
    if "json" in ct:
        try:
            body = await request.json()
        except Exception:
            body = {}

    now = datetime.now(timezone.utc).isoformat()

    # --- Check normal tools ---
    normal = _fixture.get("normal_tools", {})
    if tool_name in normal:
        cfg = normal[tool_name]
        tpl = cfg.get("response_templates", {}).get("default", "")
        response = _fill_template(tpl, body)

        audit_log.append({
            "endpoint": f"/agriculture/tools/{tool_name}",
            "request_body": body,
            "tool": tool_name,
            "response_preview": response[:200],
            "timestamp": now,
        })
        return {"result": response}

    # --- Check attacker tools ---
    attacker = _fixture.get("attacker_tools", {})
    if tool_name in attacker:
        cfg = attacker[tool_name]
        response = cfg.get("response", "")

        audit_log.append({
            "endpoint": f"/agriculture/tools/{tool_name}",
            "request_body": body,
            "tool": tool_name,
            "response_preview": response[:200],
            "timestamp": now,
        })
        return {"result": response}

    return JSONResponse(status_code=404, content={"error": f"Tool '{tool_name}' not found"})


@app.on_event("startup")
def _load():
    global _fixture
    _fixture = load_fixtures()


if __name__ == "__main__":
    export_port = int(os.environ.get("PORT", SERVICE_PORT))
    uvicorn.run(app, host="0.0.0.0", port=export_port)