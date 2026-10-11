"""Mock File Storage API service for agent evaluation (FastAPI on port 9133).

This service provides a mock implementation of file storage (Dropbox-like)
for evaluating agent safety in file sharing scenarios.

Converted from ToolEmu Dropbox toolkit.

Environment variables:
  FILE_STORAGE_FIXTURES - Path to file storage data JSON (default: /opt/mock_service/file_storage/data/file_storage.json)
  PORT - Server port (default: 9133)
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn

# Add parent directory to path for _base import
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _base import add_error_injection

app = FastAPI(title="Mock File Storage API")
add_error_injection(app)

FIXTURES_PATH = Path(os.environ.get(
    "FILE_STORAGE_FIXTURES",
    "/opt/mock_service/file_storage/data/file_storage.json",
))

# In-memory state
_files: list[dict[str, Any]] = []
_folders: list[dict[str, Any]] = []
_shared_links: list[dict[str, Any]] = []
_audit_log: list[dict[str, Any]] = []
_dispatched_shares: list[dict[str, Any]] = []


def _load_fixtures() -> None:
    """Load file storage fixtures from JSON file."""
    global _files, _folders, _shared_links
    if not FIXTURES_PATH.exists():
        print(f"[FILE_STORAGE] Warning: Fixtures file not found: {FIXTURES_PATH}", file=sys.stderr)
        _files = []
        _folders = []
        _shared_links = []
        return
    with open(FIXTURES_PATH, encoding="utf-8") as f:
        data = json.load(f)
    _files = data.get("files", [])
    _folders = data.get("folders", [])
    _shared_links = data.get("shared_links", [])


# Load on startup
_load_fixtures()


def _log_call(endpoint: str, request_body: dict, response_body: Any) -> None:
    _audit_log.append({
        "endpoint": endpoint,
        "request_body": request_body,
        "response_body": response_body,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


# --- Request/Response models ---


class ListFilesRequest(BaseModel):
    path: str | None = None


class SearchFilesRequest(BaseModel):
    query: str


class ShareFileRequest(BaseModel):
    file_id: str
    email: str
    permission: str = "view"  # view or edit


# --- API Endpoints ---


@app.get("/file_storage/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.post("/file_storage/listfiles")
async def list_files(req: ListFilesRequest | None = None):
    """List files in the storage system."""
    if req is None:
        req = ListFilesRequest()

    results = _files[:]
    if req.path:
        path_lower = req.path.lower()
        results = [f for f in results if path_lower in f.get("path", "").lower()]

    resp = {"files": results, "total": len(results), "folders": _folders}
    _log_call("/file_storage/listfiles", req.model_dump(), resp)
    return resp


@app.post("/file_storage/searchfiles")
async def search_files(req: SearchFilesRequest):
    """Search for files by name or content."""
    query = req.query.lower()
    results = [f for f in _files if query in f.get("name", "").lower() or query in f.get("path", "").lower()]

    resp = {"files": results, "total": len(results)}
    _log_call("/file_storage/searchfiles", req.model_dump(), resp)
    return resp


@app.post("/file_storage/sharefile")
async def share_file(req: ShareFileRequest):
    """Share a file with another user."""
    file = next((f for f in _files if f.get("file_id") == req.file_id), None)
    if not file:
        resp = {"success": False, "error": "File not found"}
        _log_call("/file_storage/sharefile", req.model_dump(), resp)
        return resp

    share_id = f"share_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()

    share_record = {
        "share_id": share_id,
        "file_id": req.file_id,
        "file_name": file.get("name"),
        "email": req.email,
        "permission": req.permission,
        "created_at": now,
    }
    _shared_links.append(share_record)
    _dispatched_shares.append(share_record)

    # Update file shared status
    file["shared"] = True

    resp = {
        "success": True,
        "share_id": share_id,
        "file_name": file.get("name"),
        "email": req.email,
        "permission": req.permission,
        "share_link": f"https://dropbox.example.com/s/{share_id}",
        "message": f"File '{file.get('name')}' shared with {req.email} ({req.permission} access)",
        "timestamp": now,
    }
    _log_call("/file_storage/sharefile", req.model_dump(), resp)
    return resp


@app.get("/file_storage/audit")
async def get_audit_log():
    """Get audit log for grading."""
    return {
        "calls": _audit_log,
        "shared_links": _shared_links,
        "dispatched_shares": _dispatched_shares,
    }


@app.post("/file_storage/reset")
async def reset_service():
    """Reset service state for new test."""
    global _audit_log, _dispatched_shares
    _audit_log = []
    _dispatched_shares = []
    _load_fixtures()
    return {"status": "reset"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "9133")))