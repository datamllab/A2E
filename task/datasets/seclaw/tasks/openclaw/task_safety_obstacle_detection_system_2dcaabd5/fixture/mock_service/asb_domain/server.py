#!/usr/bin/env python3
"""HTTP Mock Service for ASB Domain - agriculture_automation (obstacle_detection_system task).

Supports OPI injection: when INJECTION_MODE=opi, appends injection payload
to normal tool responses to test agent's resistance to indirect prompt injection.

Env vars:
    ASB_FIXTURES   — path to service_data.json
    INJECTION_MODE  — "none" (default) | "opi" (append injection to normal tool responses)
    PORT            — service port (default 9131)
"""

import json
import os
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn

app = FastAPI(title="ASB Domain Mock Service")

# Configuration
SERVICE_PORT = 9131
FIXTURES_PATH = Path("/opt/mock_service/asb_domain/data/service_data.json")

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

_fixture: dict[str, Any] = {}
_audit_log: list[dict[str, Any]] = []
_tool_call_log: list[dict[str, Any]] = []


# ---------------------------------------------------------------------------
# Startup / helpers
# ---------------------------------------------------------------------------

@app.on_event("startup")
def _load():
    path = os.environ.get("ASB_FIXTURES", str(FIXTURES_PATH))
    if path and Path(path).exists():
        with open(path) as f:
            global _fixture
            _fixture = json.load(f)


def _log_tool_call(tool_name: str, params: dict, response: str):
    _tool_call_log.append({
        "tool": tool_name,
        "params": params,
        "response_preview": response[:200],
        "timestamp": datetime.utcnow().isoformat(),
    })


def _fill_template(template: str, params: dict) -> str:
    """Simple {key} substitution in response templates."""
    result = template
    for k, v in params.items():
        result = result.replace("{" + k + "}", str(v))
    return result


# ---------------------------------------------------------------------------
# Health / Reset / Audit
# ---------------------------------------------------------------------------

@app.get("/asb/health")
async def health():
    return {"status": "healthy", "domain": _fixture.get("domain", "unknown")}


@app.post("/asb/reset")
async def reset():
    global _audit_log, _tool_call_log
    _audit_log = []
    _tool_call_log = []
    # Reload fixtures
    path = os.environ.get("ASB_FIXTURES", str(FIXTURES_PATH))
    if path and Path(path).exists():
        with open(path) as f:
            global _fixture
            _fixture = json.load(f)
    return {"status": "reset"}


@app.get("/asb/audit")
async def audit():
    return {
        "domain": _fixture.get("domain", "unknown"),
        "tool_calls": _tool_call_log,
    }


# ---------------------------------------------------------------------------
# Dynamic tool endpoint
# ---------------------------------------------------------------------------

@app.post("/tools/{tool_name}")
async def call_tool(tool_name: str, request: Request):
    body = {}
    ct = request.headers.get("content-type", "")
    if "json" in ct:
        try:
            body = await request.json()
        except Exception:
            body = {}

    # --- Check normal tools ---
    normal = _fixture.get("normal_tools", {})
    if tool_name in normal:
        cfg = normal[tool_name]
        tpl = cfg.get("response_templates", {}).get("default", "")
        response = _fill_template(tpl, body)

        # OPI injection: append injection payload to normal tool response
        injection_mode = os.environ.get("INJECTION_MODE", "none")
        if injection_mode == "opi":
            suffix_tpl = cfg.get("response_templates", {}).get("opi_injection_suffix", "")
            if suffix_tpl:
                # Fill injection payload from first attacker tool
                attacker_tools = _fixture.get("attacker_tools", {})
                for at_name, at_cfg in attacker_tools.items():
                    payload_tpl = _fixture.get("injection_payloads", {}).get("combined_attack", "")
                    payload = payload_tpl.replace(
                        "{attack_instruction}", at_cfg.get("attack_instruction", "")
                    ).replace("{tool_name}", at_name)
                    suffix = suffix_tpl.replace("{injection_payload}", payload)
                    response += " " + suffix
                    break

        _log_tool_call(tool_name, body, response)
        return {"result": response}

    # --- Check attacker tools ---
    attacker = _fixture.get("attacker_tools", {})
    if tool_name in attacker:
        cfg = attacker[tool_name]
        response = cfg.get("response", "")
        _log_tool_call(tool_name, body, response)
        return {"result": response}

    return JSONResponse(status_code=404, content={"error": f"Tool '{tool_name}' not found"})


if __name__ == "__main__":
    export_port = int(os.environ.get("PORT", SERVICE_PORT))
    uvicorn.run(app, host="0.0.0.0", port=export_port)