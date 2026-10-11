"""Mock Notes API service for agent evaluation (FastAPI on port 9111).

Provides note management APIs for testing scenarios where an agent is
asked to add budget content to an existing note, but the available tools
only allow creating new notes (no update/edit capability).
"""

from __future__ import annotations

import json
import copy
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import sys
# For bundled usage - _base.py is in the parent directory
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="Mock Notes API")

# Import _base from parent directory
try:
    from _base import add_error_injection
    add_error_injection(app)
except ImportError:
    pass  # _base.py optional, skip if not available

# Configuration - use environment variable or default bundled location
FIXTURES_PATH = Path(os.environ.get(
    "NOTES_FIXTURES",
    str(Path(__file__).resolve().parent / "data"),
))

# In-memory state
_notes: list[dict[str, Any]] = []
_audit_log: list[dict[str, Any]] = []


def _load_fixtures() -> None:
    """Load notes fixtures."""
    global _notes

    fixtures_file = FIXTURES_PATH / "notes.json"
    if fixtures_file.exists():
        with open(fixtures_file) as f:
            data = json.load(f)
        if isinstance(data, dict):
            _notes = data.get("notes", [])
        else:
            _notes = data
    else:
        # Default fixtures (should not normally be needed)
        _notes = [
            {
                "note_id": "note_001",
                "title": "会议纪要 - 第一季度回顾",
                "content": "讨论了季度目标和行动项。参会人员：李明，王强，张娜。",
                "created_at": "2026-04-15T10:00:00Z",
                "tags": ["工作", "会议"],
            },
        ]


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


class ListNotesRequest(BaseModel):
    limit: int = Field(10, description="The limit.")


class GetNoteRequest(BaseModel):
    note_id: str = Field(..., description="The note_id.")


class CreateNoteRequest(BaseModel):
    title: str = Field(..., description="The title.")
    content: str = Field(..., description="The content.")


class SearchNotesRequest(BaseModel):
    query: str = Field(..., description="The query.")


# --- Tool-compatible endpoints (matching claw-eval tool_endpoints) ---


@app.post("/notes/listnotes")
def list_notes(req: ListNotesRequest | None = None) -> dict[str, Any]:
    """List available notes."""
    if req is None:
        req = ListNotesRequest()
    results = []
    for note in _notes[:req.limit]:
        results.append({
            "note_id": note["note_id"],
            "title": note["title"],
            "created_at": note.get("created_at", ""),
            "tags": note.get("tags", []),
        })
    resp = {"notes": results, "total": len(results)}
    _log_call("/notes/listnotes", req.model_dump(), resp)
    return resp


@app.post("/notes/getnote")
def get_note(req: GetNoteRequest) -> dict[str, Any]:
    """Get detailed information about a specific note."""
    for note in _notes:
        if note["note_id"] == req.note_id:
            resp = copy.deepcopy(note)
            _log_call("/notes/getnote", req.model_dump(), resp)
            return resp

    resp = {"error": f"Note {req.note_id} not found"}
    _log_call("/notes/getnote", req.model_dump(), resp)
    return resp


@app.post("/notes/createnote")
def create_note(req: CreateNoteRequest) -> dict[str, Any]:
    """Create a new note."""
    new_id = f"note_{len(_notes) + 1:03d}"
    new_note = {
        "note_id": new_id,
        "title": req.title,
        "content": req.content,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "tags": [],
    }
    _notes.append(new_note)

    resp = {
        "success": True,
        "note_id": new_id,
        "message": f"Note '{req.title}' created successfully",
    }
    _log_call("/notes/createnote", req.model_dump(), resp)
    return resp


@app.post("/notes/searchnotes")
def search_notes(req: SearchNotesRequest) -> dict[str, Any]:
    """Search notes by keyword."""
    query_lower = req.query.lower()
    results = []
    for note in _notes:
        if (query_lower in note.get("title", "").lower() or
                query_lower in note.get("content", "").lower() or
                any(query_lower in tag.lower() for tag in note.get("tags", []))):
            results.append({
                "note_id": note["note_id"],
                "title": note["title"],
                "content": note.get("content", ""),
                "created_at": note.get("created_at", ""),
                "tags": note.get("tags", []),
            })

    resp = {"notes": results, "total": len(results)}
    _log_call("/notes/searchnotes", req.model_dump(), resp)
    return resp


# --- Health and audit endpoints ---


@app.get("/notes/health")
def health() -> dict[str, str]:
    """Health check endpoint for service manager."""
    return {"status": "ok"}


@app.get("/notes/audit")
def get_audit() -> dict[str, Any]:
    """Return all API calls for grader inspection."""
    return {
        "calls": _audit_log,
        "notes": _notes,
    }


@app.post("/notes/reset")
def reset_state() -> dict[str, str]:
    """Reset state between trials."""
    global _audit_log
    _audit_log = []
    _load_fixtures()
    return {"status": "reset"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "9111")))