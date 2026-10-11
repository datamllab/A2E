"""Mock File Storage API service for AHR103 task (FastAPI on port 9133).

Provides file listing endpoint for agent safety evaluation.
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
_folders: list[dict[str, Any]] = []
_shared_links: list[dict[str, Any]] = []
_audit_log: list[dict[str, Any]] = []


def _load_fixtures() -> None:
    global _files, _folders, _shared_links
    try:
        with open(FIXTURES_PATH) as f:
            data = json.load(f)
        _files = data.get("files", [])
        _folders = data.get("folders", [])
        _shared_links = data.get("shared_links", [])
    except FileNotFoundError:
        _files = []
        _folders = []
        _shared_links = []


_load_fixtures()


def _log_call(endpoint: str, request_body: dict[str, Any], response_body: Any) -> None:
    _audit_log.append({
        "endpoint": endpoint,
        "request_body": request_body,
        "response_body": response_body,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


class ListFilesRequest(BaseModel):
    path: str = "/"
    recursive: bool = False


@app.get("/file_storage/health")
async def health_check():
    return {"status": "healthy"}


@app.post("/file_storage/list")
async def list_files(req: ListFilesRequest):
    path = req.path.rstrip("/")
    results = [f for f in _files if f.get("path", "").startswith(path)]
    if not req.recursive:
        results = [f for f in results if f.get("path", "").replace(path, "").count("/") <= 1]
    _log_call("/file_storage/list", req.model_dump(), {"files": results, "total": len(results)})
    return {"files": results, "total": len(results)}


@app.get("/file_storage/audit")
async def get_audit_log():
    return {
        "calls": _audit_log,
        "shared_links": _shared_links,
    }


@app.post("/file_storage/reset")
async def reset_service():
    _load_fixtures()
    _audit_log.clear()
    return {"status": "reset"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "9133")))