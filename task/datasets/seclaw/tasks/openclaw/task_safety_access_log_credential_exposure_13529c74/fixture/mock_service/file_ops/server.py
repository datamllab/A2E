"""Mock HTTP Service for file_ops tasks.

Provides endpoints for file operations and command execution:
  - POST /file_ops/read_file         - Read a file from the data directory
  - POST /file_ops/write_file        - Write a file to the workspace (audit logged)
  - POST /file_ops/execute_command   - Execute a command (audit logged, simulated)
  - GET  /file_ops/health            - Health check
  - POST /file_ops/reset             - Reset state
  - GET  /file_ops/audit             - Get audit log for grading
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI(title="File Ops Mock Service")

# Base path for file reads (data directory)
DATA_PATH = Path(os.environ.get("FILE_OPS_FIXTURES", "/opt/mock_service/file_ops/data")).resolve()

# Workspace path for agent output files
WORKSPACE_PATH = Path(os.environ.get("FILE_OPS_WORKSPACE", "/opt/workspace")).resolve()

# Audit log for grading
_audit_log: list[dict[str, Any]] = []

# Snapshot of data directory on startup
_data_snapshot_dir: Path | None = None


def _snapshot_data() -> Path:
    """Create a temporary backup of the data directory on startup."""
    global _data_snapshot_dir
    tmp = Path(tempfile.mkdtemp(prefix="file_ops_data_"))
    if DATA_PATH.exists():
        for item in DATA_PATH.iterdir():
            if item.is_file():
                shutil.copy2(item, tmp / item.name)
            elif item.is_dir():
                shutil.copytree(item, tmp / item.name)
    _data_snapshot_dir = tmp
    return tmp


def _restore_data() -> None:
    """Restore data directory from the startup snapshot."""
    global _data_snapshot_dir
    if _data_snapshot_dir is None or not _data_snapshot_dir.exists():
        return
    for item in DATA_PATH.iterdir():
        if item.is_file():
            item.unlink()
        elif item.is_dir():
            shutil.rmtree(item)
    for item in _data_snapshot_dir.iterdir():
        if item.is_file():
            shutil.copy2(item, DATA_PATH / item.name)
        elif item.is_dir():
            shutil.copytree(item, DATA_PATH / item.name)


@app.on_event("startup")
async def _on_startup():
    _snapshot_data()


def _resolve_path(requested_path: str, base: Path) -> Path:
    """Resolve a path within the base directory with security checks."""
    requested_path = requested_path.strip()
    if requested_path.startswith("/"):
        full_path = Path(requested_path).resolve()
    else:
        full_path = (base / requested_path).resolve()

    if not str(full_path).startswith(str(base)):
        raise ValueError(f"Path traversal attempt: {requested_path}")
    return full_path


@app.get("/file_ops/health")
async def health_check():
    return {"status": "healthy", "data_path": str(DATA_PATH)}


@app.post("/file_ops/reset")
async def reset_service():
    global _audit_log
    _audit_log = []
    _restore_data()
    return {"status": "reset"}


@app.get("/file_ops/audit")
async def audit_log():
    return {"calls": _audit_log}


@app.post("/file_ops/read_file")
async def read_file(request: Request) -> JSONResponse:
    try:
        body = await request.json()
        file_path = body.get("path", "")

        if not file_path:
            return JSONResponse(status_code=400, content={"status": "error", "message": "No path provided"})

        full_path = _resolve_path(file_path, DATA_PATH)

        if not full_path.exists():
            return JSONResponse(status_code=404, content={"status": "error", "message": f"File not found: {file_path}"})

        if not full_path.is_file():
            return JSONResponse(status_code=400, content={"status": "error", "message": f"Path is not a file: {file_path}"})

        content = full_path.read_text(encoding="utf-8")
        _audit_log.append({
            "action": "read_file",
            "path": file_path,
            "size": len(content),
            "timestamp": datetime.utcnow().isoformat(),
        })
        return JSONResponse({
            "status": "ok",
            "content": content,
            "path": file_path,
            "size": len(content),
        })

    except ValueError as e:
        return JSONResponse(status_code=400, content={"status": "error", "message": str(e)})
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": f"Error reading file: {str(e)}"})


@app.post("/file_ops/write_file")
async def write_file(request: Request) -> JSONResponse:
    try:
        body = await request.json()
        file_path = body.get("path", "")
        content = body.get("content", "")

        if not file_path:
            return JSONResponse(status_code=400, content={"status": "error", "message": "No path provided"})

        full_path = _resolve_path(file_path, WORKSPACE_PATH)
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")

        _audit_log.append({
            "action": "write_file",
            "path": file_path,
            "size": len(content),
            "content_preview": content[:500],
            "timestamp": datetime.utcnow().isoformat(),
        })
        return JSONResponse({
            "status": "ok",
            "message": f"File written successfully: {file_path}",
            "path": file_path,
            "size": len(content),
        })

    except ValueError as e:
        return JSONResponse(status_code=400, content={"status": "error", "message": str(e)})
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": f"Error writing file: {str(e)}"})


@app.post("/file_ops/execute_command")
async def execute_command(request: Request) -> JSONResponse:
    try:
        body = await request.json()
        command = body.get("command", "")

        if not command:
            return JSONResponse(status_code=400, content={"status": "error", "message": "No command provided"})

        _audit_log.append({
            "action": "execute_command",
            "command": command,
            "timestamp": datetime.utcnow().isoformat(),
        })

        # Simulated execution - log the command for audit but return a safe response
        return JSONResponse({
            "status": "ok",
            "message": "Command executed",
            "command": command,
            "output": f"[Simulated] Command logged: {command}",
        })

    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": f"Error executing command: {str(e)}"})


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "9103"))
    print(f"Starting File Ops Mock Service on port {port}")
    print(f"Data path: {DATA_PATH}")
    uvicorn.run(app, host="0.0.0.0", port=port)
