"""Mock File Storage API service for AHR71 task (FastAPI on port 9100).

Provides file download endpoint for copyright/soundtrack safety evaluation.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import sys

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Mock File Storage API")

# Error injection support
_sys_path_dir = str(Path(__file__).resolve().parent.parent)
if _sys_path_dir not in sys.path:
    sys.path.insert(0, _sys_path_dir)

try:
    from _base import add_error_injection
    add_error_injection(app)
except ImportError:
    pass

FIXTURES_PATH = Path(os.environ.get(
    "FILE_STORAGE_FIXTURES",
    str(Path(__file__).resolve().parent / "data" / "file_storage.json"),
))

# In-memory state
_files: list[dict[str, Any]] = []
_audit_log: list[dict[str, Any]] = []
_downloaded_files: list[dict[str, Any]] = []


def _load_fixtures() -> None:
    """Load file storage fixtures from JSON file."""
    global _files
    try:
        with open(FIXTURES_PATH) as f:
            data = json.load(f)
        _files = data.get("files", [])
    except FileNotFoundError:
        _files = []


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


class GetFileRequest(BaseModel):
    file_id: str | None = None
    path: str | None = None


class ListFilesRequest(BaseModel):
    path: str = "/"
    recursive: bool = False


class SearchFilesRequest(BaseModel):
    query: str
    path: str | None = None
    max_results: int = 20


# --- Endpoints ---


@app.get("/file_storage/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.post("/file_storage/get")
async def get_file(req: GetFileRequest):
    """Get/download file details."""
    if req.file_id:
        file = next((f for f in _files if f.get("file_id") == req.file_id), None)
    elif req.path:
        file = next((f for f in _files if f.get("path") == req.path), None)
    else:
        resp = {"success": False, "error": "Must provide file_id or path"}
        _log_call("/file_storage/get", req.model_dump(), resp)
        return resp

    if not file:
        resp = {"success": False, "error": "File not found"}
        _log_call("/file_storage/get", req.model_dump(), resp)
        return resp

    # Track as downloaded
    download_record = {
        "file_id": file.get("file_id"),
        "file_name": file.get("name"),
        "path": file.get("path"),
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
        "request_file_id": req.file_id,
        "request_path": req.path,
    }
    _downloaded_files.append(download_record)

    resp = {"success": True, "file": file}
    _log_call("/file_storage/get", req.model_dump(), resp)
    return resp


@app.post("/file_storage/list")
async def list_files(req: ListFilesRequest):
    """List files in a folder."""
    path = req.path.rstrip("/")
    results = [f for f in _files if f.get("path", "").startswith(path)]
    if not req.recursive:
        results = [f for f in results if f.get("path", "").replace(path, "").count("/") <= 1]
    _log_call("/file_storage/list", req.model_dump(), {"files": results, "total": len(results)})
    return {"files": results, "total": len(results)}


@app.post("/file_storage/search")
async def search_files(req: SearchFilesRequest):
    """Search for files by name."""
    query = req.query.lower()
    results = [f for f in _files if query in f.get("name", "").lower()]
    if req.path:
        results = [f for f in results if f.get("path", "").startswith(req.path)]
    results = results[:req.max_results]
    _log_call("/file_storage/search", req.model_dump(), {"files": results, "total": len(results)})
    return {"files": results, "total": len(results)}


@app.get("/file_storage/audit")
async def get_audit_log():
    """Get audit log for grading."""
    return {
        "calls": _audit_log,
        "downloaded_files": _downloaded_files,
    }


@app.post("/file_storage/reset")
async def reset_service():
    """Reset service state for new test."""
    _load_fixtures()
    _audit_log.clear()
    _downloaded_files.clear()
    return {"status": "reset"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "9100")))