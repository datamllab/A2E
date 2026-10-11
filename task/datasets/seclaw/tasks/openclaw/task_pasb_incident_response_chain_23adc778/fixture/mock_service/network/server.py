"""Generic mock service for PASB network tasks.

Handles tool calls dynamically: fixture data defines per-tool responses,
and all calls are logged for grader inspection.

Env vars:
  PASB_FIXTURES  - path to fixture JSON file or directory
  PORT           - listen port (default 9131)
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI(title="PASB Network Mock Service")

# --- State ---

_fixture_data: dict = {}
_audit_log: list[dict] = []


# --- Fixture Loading ---

def _load_fixtures() -> None:
    global _fixture_data, _audit_log
    fixtures_path = os.environ.get("PASB_FIXTURES", "/opt/mock_service/network/data")
    _fixture_data = {}
    if fixtures_path:
        p = Path(fixtures_path)
        if p.is_dir():
            for f in sorted(p.glob("*.json")):
                with open(f) as fh:
                    _fixture_data.update(json.load(fh))
        elif p.is_file():
            with open(f) as fh:
                _fixture_data = json.load(fh)
    _audit_log = []


def _log_call(tool_name: str, request_body: dict, response: dict | None = None) -> None:
    _audit_log.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "tool_name": tool_name,
        "request_body": request_body,
        "response_body": response,
    })


_load_fixtures()


# --- Endpoints ---

@app.post("/pasb/{tool_name}")
async def handle_tool_call(tool_name: str, request: Request) -> JSONResponse:
    raw = await request.body()
    body = json.loads(raw) if raw else {}
    responses = _fixture_data.get("tool_responses", {})
    resp = responses.get(tool_name)
    if resp is None:
        resp = {
            "status": "ok",
            "message": f"Action '{tool_name}' completed successfully",
            "id": str(uuid.uuid4()),
        }
    _log_call(tool_name, body, resp)
    return JSONResponse(content=resp)


@app.get("/pasb/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/pasb/reset")
async def reset() -> dict:
    _load_fixtures()
    return {"status": "ok"}


@app.get("/pasb/audit")
async def audit() -> dict:
    return {"calls": _audit_log}


# --- Main ---

if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "9131"))
    uvicorn.run(app, host="0.0.0.0", port=port)