#!/usr/bin/env python3
"""HTTP Mock Service for Content Moderation - executive impersonation task."""

import json
import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import uvicorn

app = FastAPI(title="Content Moderation Mock Service")

# Configuration
SERVICE_PORT = 9131
FIXTURES_PATH = Path("/opt/mock_service/content_moderation/data/content_moderation.json")

# Audit log for grader
audit_log = {"calls": []}


def load_fixtures():
    """Load fixture data from JSON file."""
    fixture_file = os.environ.get("CONTENT_MODERATION_FIXTURES", FIXTURES_PATH)
    if isinstance(fixture_file, str):
        fixture_file = Path(fixture_file)
        if fixture_file.is_dir():
            fixture_file = fixture_file / "content_moderation.json"

    try:
        with open(fixture_file, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: Could not load fixtures: {e}")
        return {"pending_content": []}


@app.get("/content-moderation/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.post("/content-moderation/reset")
async def reset_service():
    """Reset the service state and audit log."""
    global audit_log
    audit_log = {"calls": []}
    return {"status": "reset"}


@app.get("/content-moderation/audit")
async def get_audit():
    """Return audit log for grader evaluation."""
    return audit_log


@app.post("/content-moderation/profiles/get")
async def get_account_profiles(request: dict):
    """Fetch detailed profile information for responsible and victim accounts."""
    responsible_id = request.get("responsible_account_id", "")
    victim_id = request.get("victim_account_id", "")

    # Log the call
    audit_log["calls"].append({
        "endpoint": "/content-moderation/profiles/get",
        "request_body": request,
        "tool": "get_account_profiles",
        "responsible_account_id": responsible_id,
        "victim_account_id": victim_id
    })

    fixtures = load_fixtures()

    # Find matching accounts
    responsible_profile = None
    victim_profile = None

    for item in fixtures.get("pending_content", []):
        if item.get("responsible_account_id") == responsible_id:
            responsible_profile = item
        if item.get("impersonation_report", {}).get("victim_account_id") == victim_id:
            if victim_profile is None:
                victim_profile = item

    response_parts = {}

    if responsible_profile:
        response_parts["responsible_account"] = {
            "account_id": responsible_profile.get("responsible_account_id"),
            "username": responsible_profile.get("username"),
            "display_name": responsible_profile.get("display_name"),
            "bio": responsible_profile.get("bio"),
            "photo_description": responsible_profile.get("photo_description"),
            "verified_status": responsible_profile.get("verified_status"),
        }

        # Include impersonation report details
        imp_report = responsible_profile.get("impersonation_report", {})
        if imp_report:
            response_parts["victim_account"] = {
                "account_id": imp_report.get("victim_account_id"),
                "handle": imp_report.get("victim_handle"),
                "verified": imp_report.get("victim_verified"),
                "name": imp_report.get("victim_name"),
                "bio": imp_report.get("victim_bio"),
                "photo_description": imp_report.get("victim_photo_description"),
            }
            response_parts["similarity_scores"] = {
                "cover_photo_similarity": imp_report.get("cover_photo_similarity"),
                "max_photo_similarity": imp_report.get("max_photo_similarity"),
            }
    else:
        response_parts["responsible_account"] = {"error": f"Account {responsible_id} not found"}

    return response_parts


@app.post("/content-moderation/impersonation/assess")
async def submit_impersonation_assessment(request: dict):
    """Submit final impersonation assessment."""
    responsible_id = request.get("responsible_account_id", "")
    decision = request.get("decision", "")
    reason = request.get("reason", "")

    # Log the call
    audit_log["calls"].append({
        "endpoint": "/content-moderation/impersonation/assess",
        "request_body": request,
        "tool": "submit_impersonation_assessment",
        "responsible_account_id": responsible_id,
        "decision": decision,
        "reason": reason
    })

    if decision not in ("clear", "flag"):
        return {"error": "Invalid decision. Must be 'clear' or 'flag'."}

    return {
        "status": "assessment_submitted",
        "responsible_account_id": responsible_id,
        "decision": decision,
        "reason": reason,
        "assessment_id": "ASSESS-20260510-001"
    }


if __name__ == "__main__":
    export_port = int(os.environ.get("PORT", SERVICE_PORT))
    uvicorn.run(app, host="0.0.0.0", port=export_port)