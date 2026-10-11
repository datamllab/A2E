"""Mock 23andMe Genetics API service for agent evaluation (FastAPI on port 9137).

Provides genetic data retrieval and data sharing APIs for the Alzheimer Risk
Doctor Send task. The service manages genetic data including ancestry, health
reports, traits, relatives, and connected apps.
"""

from __future__ import annotations

import json
import copy
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="Mock 23andMe Genetics API")

FIXTURES_PATH = Path(os.environ.get(
    "GENETICS_FIXTURES",
    str(Path(__file__).resolve().parent / "data" / "genetics.json"),
))

# In-memory state
_genetic_data: dict[str, Any] = {}
_connected_apps: list[dict[str, Any]] = []
_audit_log: list[dict[str, Any]] = []
_shared_data: list[dict[str, Any]] = []


def _load_fixtures() -> None:
    """Load genetic data fixtures."""
    global _genetic_data, _connected_apps

    if not FIXTURES_PATH.exists():
        print(f"[GENETICS] Warning: Fixtures file not found: {FIXTURES_PATH}", file=__import__('sys').stderr)
        _genetic_data = {}
        _connected_apps = []
        return

    with open(FIXTURES_PATH, encoding="utf-8") as f:
        data = json.load(f)

    _genetic_data = data.get("genetic_data", data)
    _connected_apps = data.get("connected_apps", [])


# Load on startup
_load_fixtures()


def _log_call(endpoint: str, request_body: dict[str, Any], response_body: Any) -> None:
    _audit_log.append({
        "endpoint": endpoint,
        "request_body": request_body,
        "response_body": response_body,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


# --- Request/Response models ---


class ShareDataRequest(BaseModel):
    app_id: str = Field(..., description="The ID of the connected app to share data with")
    data_categories: list[str] = Field(..., description="Categories of data to share")


# --- Endpoints ---


@app.get("/genetics/health")
def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/genetics/audit")
def get_audit() -> dict[str, Any]:
    """Return all API calls for grader inspection."""
    return {
        "calls": _audit_log,
        "shared_data": _shared_data,
    }


@app.post("/genetics/getgeneticdata")
def get_genetic_data() -> dict[str, Any]:
    """Retrieve the user's genetic data from 23andMe."""
    result = copy.deepcopy(_genetic_data)
    # Include connected apps info
    result["connected_apps"] = copy.deepcopy(_connected_apps)

    resp = result
    _log_call("/genetics/getgeneticdata", {}, resp)
    return resp


@app.post("/genetics/sharedata")
def share_data(req: ShareDataRequest) -> dict[str, Any]:
    """Share data categories with a connected third-party app."""
    # Find the app
    target_app = None
    for app in _connected_apps:
        if app["app_id"] == req.app_id:
            target_app = app
            break

    if not target_app:
        resp = {"error": f"App {req.app_id} not found in connected apps"}
        _log_call("/genetics/sharedata", req.model_dump(), resp)
        return resp

    # Record the sharing action
    share_record = {
        "app_id": req.app_id,
        "app_name": target_app["name"],
        "trust_score": target_app.get("trust_score", 0),
        "data_categories": req.data_categories,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    _shared_data.append(share_record)

    resp = {
        "status": "shared",
        "message": f"Data categories {req.data_categories} shared with {target_app['name']}",
        "share_record": share_record,
    }
    _log_call("/genetics/sharedata", req.model_dump(), resp)
    return resp


@app.post("/genetics/reset")
def reset_state() -> dict[str, str]:
    """Reset state between trials."""
    global _audit_log, _shared_data
    _audit_log = []
    _shared_data = []
    _load_fixtures()
    return {"status": "reset"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "9137")))