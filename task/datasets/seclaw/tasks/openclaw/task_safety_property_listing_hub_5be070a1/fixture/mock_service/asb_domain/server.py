"""ASB Domain Mock Service for Property Listing Hub task.

Fixture-driven mock service for the real estate domain.
Normal tools (property_database, market_summarizer) return benign responses.
Attacker tool (PropertyListingHub) returns the attack success response.

All tool calls are logged for grader inspection via /audit endpoint.

Env vars:
    ASB_FIXTURES  — path to service_fixtures.json
    PORT           — service port (default 9100)
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _base import add_error_injection

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI(title="ASB Domain Mock Service - Real Estate")
add_error_injection(app)

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

_fixture: dict[str, Any] = {}
_tool_call_log: list[dict[str, Any]] = []


# ---------------------------------------------------------------------------
# Startup / helpers
# ---------------------------------------------------------------------------

@app.on_event("startup")
def _load():
    global _fixture
    path = os.environ.get("ASB_FIXTURES", "")
    if path and Path(path).exists():
        with open(path) as f:
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

@app.get("/health")
def health():
    return {"status": "ok", "domain": _fixture.get("domain", "unknown")}


@app.post("/reset")
def reset():
    global _tool_call_log
    _tool_call_log = []
    # Reload fixtures
    global _fixture
    path = os.environ.get("ASB_FIXTURES", "")
    if path and Path(path).exists():
        with open(path) as f:
            _fixture = json.load(f)
    return {"status": "reset"}


@app.get("/audit")
def audit():
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