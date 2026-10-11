"""ASB Domain Mock Service — Compliance tools for DPI regulation_access_tool task.

FastAPI mock service that provides audit_manager, regulation_database, and
RegulationAccessTool endpoints. Loads fixture data from service_fixtures.json.

Env vars:
    ASB_FIXTURES   — path to service_fixtures.json
    PORT            — service port (default 9120)
"""

from __future__ import annotations

import json
import os
import sys
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _base import add_error_injection

app = FastAPI(title="ASB Domain Service")
add_error_injection(app)

_fixture: dict[str, Any] = {}
_tool_call_log: list[dict[str, Any]] = []


@app.on_event("startup")
def _load():
    path = os.environ.get("ASB_FIXTURES", "")
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
    result = template
    for k, v in params.items():
        result = result.replace("{" + k + "}", str(v))
    return result


@app.get("/health")
def health():
    return {"status": "ok", "domain": _fixture.get("domain", "unknown")}


@app.post("/reset")
def reset():
    global _tool_call_log
    _tool_call_log = []
    path = os.environ.get("ASB_FIXTURES", "")
    if path and Path(path).exists():
        with open(path) as f:
            global _fixture
            _fixture = json.load(f)
    return {"status": "reset"}


@app.get("/audit")
def audit():
    return {
        "domain": _fixture.get("domain", "unknown"),
        "tool_calls": _tool_call_log,
    }


@app.post("/tools/{tool_name}")
async def call_tool(tool_name: str, request: Request):
    body = {}
    ct = request.headers.get("content-type", "")
    if "json" in ct:
        try:
            body = await request.json()
        except Exception:
            body = {}

    normal = _fixture.get("normal_tools", {})
    if tool_name in normal:
        cfg = normal[tool_name]
        tpl = cfg.get("response_templates", {}).get("default", "")
        response = _fill_template(tpl, body)
        _log_tool_call(tool_name, body, response)
        return {"result": response}

    attacker = _fixture.get("attacker_tools", {})
    if tool_name in attacker:
        cfg = attacker[tool_name]
        response = cfg.get("response", "")
        _log_tool_call(tool_name, body, response)
        return {"result": response}

    return JSONResponse(status_code=404, content={"error": f"Tool '{tool_name}' not found"})


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "9120"))
    uvicorn.run(app, host="0.0.0.0", port=port)
