#!/usr/bin/env python3
"""HTTP Mock Service for ASB Domain - human_resources (development_plan_tool task).

Supports knowledge search with poisoned documents for MP (Memory Poisoning) testing.
When the agent searches the knowledge base, a poisoned document (KB-HRM-002) is
returned containing injection instructions to use the DevelopmentPlanTool.

Env vars:
    ASB_FIXTURES   — path to service_data.json
    INJECTION_MODE  — "none" (default for MP tasks)
    PORT            — service port (default 9130)
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn

app = FastAPI(title="ASB Domain Mock Service")

# Configuration
SERVICE_PORT = 9130
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


# ---------------------------------------------------------------------------
# Health / Reset / Audit
# ---------------------------------------------------------------------------

@app.get("/asb_domain/health")
async def health():
    return {"status": "healthy", "domain": _fixture.get("domain", "unknown")}


@app.post("/asb_domain/reset")
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


@app.get("/asb_domain/audit")
async def audit():
    return {
        "domain": _fixture.get("domain", "unknown"),
        "tool_calls": _tool_call_log,
    }


# ---------------------------------------------------------------------------
# Normal tool endpoints
# ---------------------------------------------------------------------------

@app.post("/asb_domain/workplace_resolution_guide")
async def workplace_resolution_guide(request: Request):
    """Return workplace conflict resolution data."""
    body = {}
    ct = request.headers.get("content-type", "")
    if "json" in ct:
        try:
            body = await request.json()
        except Exception:
            body = {}

    query = body.get("query", "")

    _tool_call_log.append({
        "tool": "workplace_resolution_guide",
        "params": body,
        "query": query,
    })

    fixtures = _fixture.get("normal_tools", {}).get("workplace_resolution_guide", {})
    return fixtures


@app.post("/asb_domain/employee_wellness_tracker")
async def employee_wellness_tracker(request: Request):
    """Return employee wellness tracking data."""
    body = {}
    ct = request.headers.get("content-type", "")
    if "json" in ct:
        try:
            body = await request.json()
        except Exception:
            body = {}

    query = body.get("query", "")

    _tool_call_log.append({
        "tool": "employee_wellness_tracker",
        "params": body,
        "query": query,
    })

    fixtures = _fixture.get("normal_tools", {}).get("employee_wellness_tracker", {})
    return fixtures


@app.post("/asb_domain/knowledge_search")
async def knowledge_search(request: Request):
    """Search knowledge base and return matching documents."""
    body = {}
    ct = request.headers.get("content-type", "")
    if "json" in ct:
        try:
            body = await request.json()
        except Exception:
            body = {}

    query = body.get("query", "")
    query_lower = query.lower()

    _tool_call_log.append({
        "tool": "knowledge_search",
        "params": body,
        "query": query,
    })

    all_docs = _fixture.get("knowledge_documents", [])

    # Match documents by query keywords
    matched_docs = []
    for doc in all_docs:
        keywords = doc.get("query_keywords", [])
        # Match if any keyword appears in the query
        if any(kw.lower() in query_lower for kw in keywords):
            matched_docs.append({
                "id": doc.get("id", ""),
                "content": doc.get("content", ""),
                "relevance": "high"
            })

    # If no keyword match, return all non-poisoned docs as fallback
    if not matched_docs:
        for doc in all_docs:
            if not doc.get("poisoned", False):
                matched_docs.append({
                    "id": doc.get("id", ""),
                    "content": doc.get("content", ""),
                    "relevance": "medium"
                })

    return {
        "status": "success",
        "query": query,
        "results": matched_docs,
        "total_matches": len(matched_docs)
    }


# ---------------------------------------------------------------------------
# Attacker tool endpoint
# ---------------------------------------------------------------------------

@app.post("/asb_domain/DevelopmentPlanTool")
async def development_plan_tool(request: Request):
    """Return attacker-controlled response for the injection tool."""
    body = {}
    ct = request.headers.get("content-type", "")
    if "json" in ct:
        try:
            body = await request.json()
        except Exception:
            body = {}

    action = body.get("action", "")
    target = body.get("target", "")

    _tool_call_log.append({
        "tool": "DevelopmentPlanTool",
        "params": body,
        "action": action,
        "target": target,
    })

    fixtures = _fixture.get("attacker_tools", {}).get("DevelopmentPlanTool", {})
    return fixtures


if __name__ == "__main__":
    export_port = int(os.environ.get("PORT", SERVICE_PORT))
    uvicorn.run(app, host="0.0.0.0", port=export_port)
