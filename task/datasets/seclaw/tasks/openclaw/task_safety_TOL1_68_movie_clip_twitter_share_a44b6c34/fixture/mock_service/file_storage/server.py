"""HTTP Mock Service for file_storage (Dropbox-like).

Provides endpoints for file listing, searching, and sharing operations.
Maintains an audit log for grader inspection.
"""

import json
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn

app = FastAPI()

# Load fixture data
FIXTURES_PATH = os.environ.get(
    "FILE_STORAGE_FIXTURES",
    "/opt/mock_service/file_storage/data/file_storage.json"
)

_audit_log: list[dict[str, Any]] = []
_data: dict[str, Any] = {}


def _load_data():
    """Load fixture data from JSON file."""
    global _data
    fixtures = Path(FIXTURES_PATH)
    if fixtures.exists():
        with open(fixtures, "r", encoding="utf-8") as f:
            _data = json.load(f)
    else:
        _data = {"files": [], "folders": [], "shared_links": []}


# Load data on startup
_load_data()


@app.post("/file_storage/listfiles")
async def list_files(request: Request):
    """List files and folders in storage, optionally filtered by path."""
    body = await request.json() if request.headers.get("content-type") == "application/json" else {}
    path_filter = body.get("path", "")

    _audit_log.append({
        "endpoint": "/file_storage/listfiles",
        "request_body": body,
    })

    files = _data.get("files", [])
    folders = _data.get("folders", [])

    if path_filter:
        files = [f for f in files if path_filter in f.get("path", "")]
        folders = [f for f in folders if path_filter in f.get("path", "")]

    return JSONResponse({
        "files": files,
        "folders": folders,
    })


@app.post("/file_storage/searchfiles")
async def search_files(request: Request):
    """Search for files by name or path."""
    body = await request.json()
    query = body.get("query", "").lower()

    _audit_log.append({
        "endpoint": "/file_storage/searchfiles",
        "request_body": body,
    })

    files = _data.get("files", [])
    if query:
        results = [
            f for f in files
            if query in f.get("name", "").lower() or query in f.get("path", "").lower()
        ]
    else:
        results = files

    return JSONResponse({"files": results})


@app.post("/file_storage/sharefile")
async def share_file(request: Request):
    """Create a share link for a file."""
    body = await request.json()
    file_id = body.get("file_id", "")
    email = body.get("email", "")

    _audit_log.append({
        "endpoint": "/file_storage/sharefile",
        "request_body": body,
    })

    files = _data.get("files", [])
    target_file = None
    for f in files:
        if f.get("file_id") == file_id:
            target_file = f
            break

    if not target_file:
        return JSONResponse({"error": f"File not found: {file_id}"}, status_code=404)

    # Create share link
    share_id = f"share_{len(_data.get('shared_links', [])) + 1:03d}"
    share_link = {
        "share_id": share_id,
        "file_id": file_id,
        "email": email,
        "permission": "view",
        "url": f"https://dropbox.example.com/s/{share_id}",
        "created_at": "2026-06-05T12:00:00Z",
    }

    _data.setdefault("shared_links", []).append(share_link)

    # Update file shared status
    target_file["shared"] = True

    return JSONResponse({
        "status": "success",
        "share_link": share_link,
    })


@app.get("/file_storage/health")
async def health():
    """Health check endpoint."""
    return JSONResponse({"status": "ok"})


@app.post("/file_storage/reset")
async def reset():
    """Reset service state by reloading fixtures."""
    global _audit_log
    _audit_log = []
    _load_data()
    return JSONResponse({"status": "reset"})


@app.get("/file_storage/audit")
async def audit():
    """Return audit log for grader inspection."""
    return JSONResponse({
        "calls": _audit_log,
        "state": {
            "shared_links": _data.get("shared_links", []),
            "files": _data.get("files", []),
        },
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "9133"))
    uvicorn.run(app, host="0.0.0.0", port=port)