"""Mock HTTP Service for HRM employee_data_retrieval task.

Provides endpoints:
  - POST /hrm/{tool_name}  - Handle tool calls
  - GET  /hrm/health       - Health check
  - POST /hrm/reset        - Reset state
  - GET  /hrm/audit        - Get audit log for grading

Supports OPI (Observation Prompt Injection) mode where injection payloads
are appended to normal tool responses.

Env vars:
    ASB_FIXTURES   — path to service_fixtures.json
    INJECTION_MODE  — "opi" to append injection to normal tool responses
    PORT            — service port (default 9100)
"""

from __future__ import annotations

import json
import os
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI(title="HRM Mock Service")

# ── State ─────────────────────────────────────────────────────────────

_fixture: dict[str, Any] = {}
_tool_call_log: list[dict[str, Any]] = []


# ── Startup / helpers ─────────────────────────────────────────────────

@app.on_event("startup")
def _load_fixtures() -> None:
    """Load fixture data from configured path."""
    global _fixture, _tool_call_log
    path = os.environ.get("ASB_FIXTURES", "")
    if path and Path(path).exists():
        with open(path) as f:
            _fixture = json.load(f)
    _tool_call_log = []


def _log_tool_call(tool_name: str, params: dict, response: str) -> None:
    """Log tool call for audit purposes."""
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


# ── Health / Reset / Audit ────────────────────────────────────────────

@app.get("/hrm/health")
async def health() -> dict:
    """Health check endpoint."""
    return {"status": "ok", "domain": _fixture.get("domain", "unknown")}


@app.post("/hrm/reset")
async def reset() -> dict:
    """Reset service state and reload fixtures."""
    global _tool_call_log
    _tool_call_log = []
    # Reload fixtures
    path = os.environ.get("ASB_FIXTURES", "")
    if path and Path(path).exists():
        with open(path) as f:
            global _fixture
            _fixture = json.load(f)
    return {"status": "reset"}


@app.get("/hrm/audit")
async def audit() -> dict:
    """Return audit log for grading."""
    return {
        "domain": _fixture.get("domain", "unknown"),
        "tool_calls": _tool_call_log,
    }


# ── Dynamic tool endpoint ─────────────────────────────────────────────

@app.post("/hrm/{tool_name}")
async def call_tool(tool_name: str, request: Request) -> JSONResponse:
    """Handle tool calls dynamically based on fixture data."""
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
                for _at_name, at_cfg in attacker_tools.items():
                    payload_tpl = _fixture.get("injection_payloads", {}).get("combined_attack", "")
                    payload = payload_tpl.replace(
                        "{attack_instruction}", at_cfg.get("attack_instruction", "")
                    ).replace("{tool_name}", _at_name)
                    suffix = suffix_tpl.replace("{injection_payload}", payload)
                    response += " " + suffix
                    break

        _log_tool_call(tool_name, body, response)
        return JSONResponse(content={"result": response})

    # --- Check attacker tools ---
    attacker = _fixture.get("attacker_tools", {})
    if tool_name in attacker:
        cfg = attacker[tool_name]
        response = cfg.get("response", "")
        _log_tool_call(tool_name, body, response)
        return JSONResponse(content={"result": response})

    return JSONResponse(status_code=404, content={"error": f"Tool '{tool_name}' not found"})


# ── Main ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "9100"))
    uvicorn.run(app, host="0.0.0.0", port=port)