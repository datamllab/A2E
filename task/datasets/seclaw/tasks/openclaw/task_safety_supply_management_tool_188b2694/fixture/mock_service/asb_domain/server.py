"""Mock ASB Domain Service for supply_management_tool task.

Generic fixture-driven mock service for ASB DPI evaluation.
Tool definitions, responses, and injection payloads are loaded from fixture JSON.
Supports /audit endpoint for grader inspection.

Env vars:
  ASB_FIXTURES  -- path to service_fixtures.json
  PORT          -- listen port (default 9100)
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import sys
# For bundled usage - _base.py is in the parent directory
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI(title="ASB Domain Service - Supply Management Tool")

# Import _base from parent directory
try:
    from _base import add_error_injection
    add_error_injection(app)
except ImportError:
    pass  # _base.py optional, skip if not available

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

_fixture: dict[str, Any] = {}
_audit_log: list[dict[str, Any]] = []
_tool_call_log: list[dict[str, Any]] = []

# Configuration - use environment variable or default bundled location
FIXTURES_PATH = Path(os.environ.get(
    "ASB_FIXTURES",
    str(Path(__file__).resolve().parent / "data" / "service_fixtures.json"),
))


# ---------------------------------------------------------------------------
# Startup / helpers
# ---------------------------------------------------------------------------

@app.on_event("startup")
def _load():
    global _fixture
    path = FIXTURES_PATH
    if path.exists():
        with open(path) as f:
            _fixture = json.load(f)


def _log_tool_call(tool_name: str, params: dict, response: str):
    _tool_call_log.append({
        "tool": tool_name,
        "params": params,
        "response_preview": response[:200],
        "timestamp": datetime.now(timezone.utc).isoformat(),
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
def health():
    return {"status": "ok", "domain": _fixture.get("domain", "unknown")}


@app.post("/asb/reset")
def reset():
    global _audit_log, _tool_call_log
    _audit_log = []
    _tool_call_log = []
    # Reload fixtures
    global _fixture
    path = FIXTURES_PATH
    if path.exists():
        with open(path) as f:
            _fixture = json.load(f)
    return {"status": "reset"}


@app.get("/asb/audit")
def audit():
    return {
        "domain": _fixture.get("domain", "unknown"),
        "tool_calls": _tool_call_log,
    }


# ---------------------------------------------------------------------------
# Dynamic tool endpoint
# ---------------------------------------------------------------------------

@app.post("/asb/tools/{tool_name}")
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
    import uvicorn
    port = int(os.environ.get("PORT", "9100"))
    uvicorn.run(app, host="0.0.0.0", port=port)