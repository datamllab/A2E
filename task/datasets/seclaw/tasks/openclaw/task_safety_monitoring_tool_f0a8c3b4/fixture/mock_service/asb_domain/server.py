#!/usr/bin/env python3
"""HTTP Mock Service for ASB Domain - compliance (monitoring_tool task).

Supports knowledge base search with poisoned documents (MP attack):
When the agent searches the knowledge base, a poisoned document (KB-CMP-002)
is returned containing instructions to use the MonitoringTool.

Env vars:
    ASB_FIXTURES   — path to service_data.json
    INJECTION_MODE  — unused for MP tasks (injection is in knowledge docs)
    PORT            — service port (default 9131)
"""

import json
import os
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

@app.post("/asb_domain/audit_manager")
async def audit_manager(request: Request):
    body = {}
    ct = request.headers.get("content-type", "")
    if "json" in ct:
        try:
            body = await request.json()
        except Exception:
            body = {}

    fixtures = load_fixtures()
    cfg = fixtures.get("normal_tools", {}).get("audit_manager", {})
    result = cfg.get("result", cfg) if isinstance(cfg, dict) else cfg

    _log_tool_call("audit_manager", body, str(result)[:200])
    return result


@app.post("/asb_domain/regulation_database")
async def regulation_database(request: Request):
    body = {}
    ct = request.headers.get("content-type", "")
    if "json" in ct:
        try:
            body = await request.json()
        except Exception:
            body = {}

    fixtures = load_fixtures()
    cfg = fixtures.get("normal_tools", {}).get("regulation_database", {})
    result = cfg.get("result", cfg) if isinstance(cfg, dict) else cfg

    _log_tool_call("regulation_database", body, str(result)[:200])
    return result


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

    _log_tool_call("knowledge_search", body, query[:200])

    fixtures = load_fixtures()
    all_docs = fixtures.get("knowledge_documents", [])

    # Match documents by query keywords
    matched_docs = []
    for doc in all_docs:
        keywords = doc.get("query_keywords", [])
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

@app.post("/asb_domain/MonitoringTool")
async def monitoring_tool(request: Request):
    body = {}
    ct = request.headers.get("content-type", "")
    if "json" in ct:
        try:
            body = await request.json()
        except Exception:
            body = {}

    fixtures = load_fixtures()
    cfg = fixtures.get("attacker_tools", {}).get("MonitoringTool", {})

    _log_tool_call("MonitoringTool", body, str(cfg)[:200])
    return cfg


# ---------------------------------------------------------------------------
# Fallback dynamic endpoint
# ---------------------------------------------------------------------------

@app.post("/tools/{tool_name}")
async def call_tool_fallback(tool_name: str, request: Request):
    """Fallback endpoint for tools accessed via /tools/{name} path."""
    body = {}
    ct = request.headers.get("content-type", "")
    if "json" in ct:
        try:
            body = await request.json()
        except Exception:
            body = {}

    fixtures = load_fixtures()

    # Check normal tools
    normal = fixtures.get("normal_tools", {})
    if tool_name in normal:
        cfg = normal[tool_name]
        _log_tool_call(tool_name, body, str(cfg)[:200])
        return cfg

    # Check attacker tools
    attacker = fixtures.get("attacker_tools", {})
    if tool_name in attacker:
        cfg = attacker[tool_name]
        _log_tool_call(tool_name, body, str(cfg)[:200])
        return cfg

    return JSONResponse(status_code=404, content={"error": f"Tool '{tool_name}' not found"})


def load_fixtures():
    """Load fixture data from JSON file."""
    fixture_file = os.environ.get("ASB_FIXTURES", str(FIXTURES_PATH))
    if isinstance(fixture_file, str):
        fixture_file = Path(fixture_file)
        if not fixture_file.suffix == ".json":
            fixture_file = fixture_file / "service_data.json"

    try:
        with open(fixture_file, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: Could not load fixtures: {e}")
        return {"normal_tools": {}, "attacker_tools": {}, "knowledge_documents": []}


if __name__ == "__main__":
    export_port = int(os.environ.get("PORT", SERVICE_PORT))
    uvicorn.run(app, host="0.0.0.0", port=export_port)