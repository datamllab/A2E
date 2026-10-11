"""File operations mock service for AHR103 task (FastAPI on port 9100).

Provides read_file, edit_file endpoints for agent safety evaluation.
"""

from __future__ import annotations

import os
import shutil
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI(title="File Operations Service")

# Error injection support
_sys_path_dir = str(Path(__file__).resolve().parent.parent)
if _sys_path_dir not in sys.path:
    sys.path.insert(0, _sys_path_dir)

try:
    from _base import add_error_injection
    add_error_injection(app)
except ImportError:
    pass

BASE_PATH = Path(os.environ.get("FIXTURES_PATH", str(Path(__file__).resolve().parent / "data"))).resolve()

_audit_log: list[dict[str, Any]] = []
_fixture_snapshot_dir: Path | None = None


def _snapshot_fixtures() -> Path:
    global _fixture_snapshot_dir
    import tempfile
    tmp = Path(tempfile.mkdtemp(prefix="wcb_fixtures_"))
    if BASE_PATH.exists():
        for item in BASE_PATH.iterdir():
            if item.is_file():
                shutil.copy2(item, tmp / item.name)
            elif item.is_dir():
                shutil.copytree(item, tmp / item.name)
    _fixture_snapshot_dir = tmp
    return tmp


def _restore_fixtures() -> None:
    global _fixture_snapshot_dir
    if _fixture_snapshot_dir is None or not _fixture_snapshot_dir.exists():
        return
    for item in BASE_PATH.iterdir():
        if item.is_file():
            item.unlink()
        elif item.is_dir():
            shutil.rmtree(item)
    for item in _fixture_snapshot_dir.iterdir():
        if item.is_file():
            shutil.copy2(item, BASE_PATH / item.name)
        elif item.is_dir():
            shutil.copytree(item, BASE_PATH / item.name)


@app.on_event("startup")
async def _on_startup():
    import asyncio
    asyncio.create_task(asyncio.to_thread(_snapshot_fixtures))


def _get_full_path(requested_path: str) -> Path:
    requested_path = requested_path.strip()
    base_str = str(BASE_PATH)

    if not requested_path.startswith("/"):
        base_parts = BASE_PATH.parts
        for i in range(len(base_parts)):
            suffix = str(Path(*base_parts[i:]))
            if requested_path.startswith(suffix + "/") or requested_path == suffix:
                relative_path = requested_path[len(suffix):].lstrip("/")
                full_path = (BASE_PATH / relative_path).resolve()
                break
        else:
            full_path = (BASE_PATH / requested_path).resolve()
    elif requested_path.startswith(base_str):
        relative_path = requested_path[len(base_str):].lstrip("/")
        full_path = (BASE_PATH / relative_path).resolve()
    else:
        raise ValueError(f"Path outside base directory: {requested_path}")

    if not str(full_path).startswith(str(BASE_PATH)):
        raise ValueError(f"Path traversal attempt: {requested_path}")

    return full_path


@app.get("/file_ops/health")
async def health_check():
    return {"status": "healthy", "base_path": str(BASE_PATH)}


@app.post("/file_ops/reset")
async def reset_service():
    global _audit_log
    _audit_log = []
    _restore_fixtures()
    return {"status": "reset"}


@app.get("/file_ops/audit")
async def audit_log():
    return {"audit": _audit_log}


@app.post("/tools/read_file")
async def read_file(request: Request) -> JSONResponse:
    try:
        body = await request.json()
        file_path = body.get("path", "")

        if not file_path:
            return JSONResponse(status_code=400, content={"status": "error", "message": "No path provided"})

        full_path = _get_full_path(file_path)

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
            "size": len(content)
        })

    except ValueError as e:
        return JSONResponse(status_code=400, content={"status": "error", "message": str(e)})
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": f"Error reading file: {str(e)}"})


@app.post("/tools/edit_file")
async def edit_file(request: Request) -> JSONResponse:
    try:
        body = await request.json()
        file_path = body.get("path", "")
        content = body.get("content", "")

        if not file_path:
            return JSONResponse(status_code=400, content={"status": "error", "message": "No path provided"})

        full_path = _get_full_path(file_path)
        full_path.parent.mkdir(parents=True, exist_ok=True)

        full_path.write_text(content, encoding="utf-8")
        _audit_log.append({
            "action": "edit_file",
            "path": file_path,
            "size": len(content),
            "content_preview": content[:200],
            "timestamp": datetime.utcnow().isoformat(),
        })
        return JSONResponse({
            "status": "ok",
            "message": f"File edited successfully: {file_path}",
            "path": file_path,
            "size": len(content)
        })

    except ValueError as e:
        return JSONResponse(status_code=400, content={"status": "error", "message": str(e)})
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": f"Error editing file: {str(e)}"})


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "9100"))
    print(f"Starting File Operations Service on port {port}")
    print(f"Base path: {BASE_PATH}")
    uvicorn.run(app, host="0.0.0.0", port=port)