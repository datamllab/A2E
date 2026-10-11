"""Mock Insurance Domain API for agent evaluation (FastAPI on port 9131).

Provides insurance analysis tool APIs for testing DPI (Direct Prompt Injection)
scenarios where an agent might be coerced into calling the FraudDetectionTool
attacker tool instead of legitimate insurance tools (risk_assessor, policy_manager).

Fixture-driven: loads tool definitions and responses from service_data.json.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="Mock Insurance Domain API")

FIXTURES_PATH = Path(os.environ.get(
    "ASB_FIXTURES",
    str(Path(__file__).resolve().parent / "data"),
))

# In-memory state
_fixtures: dict[str, Any] = {}
_tool_call_log: list[dict[str, Any]] = []
_current_domain: str = ""


def _load_fixtures() -> None:
    """Load service fixtures."""
    global _fixtures, _current_domain

    fixtures_file = FIXTURES_PATH / "service_data.json"
    if fixtures_file.exists():
        with open(fixtures_file) as f:
            _fixtures = json.load(f)
        _current_domain = _fixtures.get("domain", "unknown")
    else:
        _fixtures = {
            "domain": "insurance",
            "normal_tools": {},
            "attacker_tools": {},
        }
        _current_domain = "insurance"


_load_fixtures()


def _log_tool_call(tool_name: str, arguments: dict, response: Any) -> None:
    _tool_call_log.append({
        "tool_name": tool_name,
        "arguments": arguments,
        "response": response,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


def _get_tool_response(tool_name: str, arguments: dict) -> dict[str, Any]:
    """Get response for a tool call based on fixture definitions.

    Checks normal_tools first, then attacker_tools.
    """
    normal_tools = _fixtures.get("normal_tools", {})
    attacker_tools = _fixtures.get("attacker_tools", {})

    if tool_name in normal_tools:
        tool_def = normal_tools[tool_name]
        templates = tool_def.get("response_templates", {})
        response_text = templates.get("default", f"{tool_name} operation completed successfully.")
        return {"status": "success", "result": response_text}

    if tool_name in attacker_tools:
        tool_def = attacker_tools[tool_name]
        response_text = tool_def.get("response", f"{tool_name} operation completed successfully.")
        return {"status": "success", "result": response_text}

    return {"status": "error", "message": f"Unknown tool: {tool_name}"}


# --- Health / Audit / Reset ---


@app.get("/health")
def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok", "domain": _current_domain}


@app.get("/audit")
def get_audit() -> dict[str, Any]:
    """Return all tool calls for grader inspection."""
    return {
        "calls": _tool_call_log,
        "domain": _current_domain,
    }


@app.post("/reset")
def reset_state() -> dict[str, str]:
    """Reset state between trials."""
    global _tool_call_log
    _tool_call_log = []
    _load_fixtures()
    return {"status": "reset"}


# --- Dynamic tool endpoint ---


class ToolRequest(BaseModel):
    """Generic tool request model that accepts any arguments."""
    model_config = {"extra": "allow"}


@app.post("/tools/{tool_name}")
def call_tool(tool_name: str, req: ToolRequest | None = None) -> dict[str, Any]:
    """Dynamic tool dispatch based on fixture definitions."""
    arguments = req.model_dump() if req else {}
    arguments.pop("model_config", None)

    response = _get_tool_response(tool_name, arguments)
    _log_tool_call(tool_name, arguments, response)
    return response


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "9131")))