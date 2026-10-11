"""Mock File Storage API service for AHR96 task (FastAPI on port 9133).

Provides file/image download endpoint for agent safety evaluation.
"""

from __future__ import annotations

import json
import os
import uuid
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
_files: list[dict[str, Any]] = {}
_audit_log: list[dict[str, Any]] = []
_downloaded_files: list[dict[str, Any]] = []


def _load_fixtures() -> None:
    """Load file storage fixtures from JSON file."""
    global _files

    if not FIXTURES_PATH.exists():
        print(f"[FILE_STORAGE] Warning: Fixtures file not found: {FIXTURES_PATH}", file=sys.stderr)
        _files = {}
        return

    with open(FIXTURES_PATH) as f:
        _files = json.load(f)
    _downloaded_files.clear()


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
    file_id: str


# --- Endpoints ---


@app.get("/file_storage/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.post("/file_storage/get")
async def get_file(req: GetFileRequest):
    """Download/get a file by ID."""
    file_id = req.file_id
    file_id_lower = file_id.lower()

    # Search in fixtures for matching file
    files_list = _files.get("files", []) if isinstance(_files, dict) else _files
    for f in files_list:
        if f.get("file_id", "").lower() == file_id_lower or f.get("name", "").lower() == file_id_lower:
            result = {
                "success": True,
                "file_id": f.get("file_id", file_id),
                "name": f.get("name", "image.jpg"),
                "size": f.get("size", 1024),
                "type": f.get("type", "image/jpeg"),
                "url": f.get("url", ""),
                "downloaded_at": datetime.now(timezone.utc).isoformat(),
            }
            _downloaded_files.append(result)
            _log_call("/file_storage/get", req.model_dump(), result)
            return result

    # If no match, return a generic file
    result = {
        "success": True,
        "file_id": file_id,
        "name": "downloaded_image.jpg",
        "size": 2048,
        "type": "image/jpeg",
        "url": f"https://storage.example.com/{file_id}",
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
    }
    _downloaded_files.append(result)
    _log_call("/file_storage/get", req.model_dump(), result)
    return result


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
    global _audit_log, _downloaded_files
    _audit_log = []
    _downloaded_files = []
    _load_fixtures()
    return {"status": "reset"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "9133")))