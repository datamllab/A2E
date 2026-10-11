"""Mock Content Generation API service for AHR24 task (FastAPI on port 9112).

Provides story template filling endpoint for agent safety evaluation.
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
from pydantic import BaseModel, Field

app = FastAPI(title="Mock Content Generation API")

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
    "CONTENT_GEN_FIXTURES",
    str(Path(__file__).resolve().parent / "data" / "content_gen.json"),
))

# In-memory state
_fixtures: dict[str, Any] = {}
_audit_log: list[dict[str, Any]] = []
_generated_stories: list[dict[str, Any]] = []


def _load_fixtures() -> None:
    global _fixtures
    if FIXTURES_PATH.exists():
        with open(FIXTURES_PATH) as f:
            _fixtures = json.load(f)
    else:
        _fixtures = {}


_load_fixtures()


def _log_call(endpoint: str, request_body: dict[str, Any], response_body: Any) -> None:
    _audit_log.append({
        "endpoint": endpoint,
        "request_body": request_body,
        "response_body": response_body,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


def _content_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


# --- Request models ---


class StoryRequest(BaseModel):
    template: str = Field(..., description="Story template to fill in")
    characters: str = Field(..., description="Description of characters to include")
    genre: str = Field(..., description="Genre of the story")
    style: str | None = Field(None, description="Writing style to use")


# --- Endpoints ---


@app.get("/content-gen/health")
def health() -> dict[str, str]:
    """Health-check probe."""
    return {"status": "ok"}


@app.post("/content-gen/story")
def fill_in_story_template(req: StoryRequest) -> dict[str, Any]:
    """Generate a story by filling in a template with specified content."""
    story_id = _content_id("story")
    content = {
        "story_id": story_id,
        "type": "story",
        "template": req.template,
        "characters": req.characters,
        "genre": req.genre,
        "style": req.style,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    _generated_stories.append(content)

    settings = _fixtures.get("default_settings", {})
    resp = {
        "success": True,
        "story_id": story_id,
        "template": req.template,
        "characters": req.characters,
        "genre": req.genre,
        "style": req.style,
        "output_path": settings.get("output_path", "/home/stories/generated_story.txt"),
        "generated_at": content["generated_at"],
    }
    _log_call("/content-gen/story", req.model_dump(), resp)
    return resp


@app.get("/content-gen/audit")
def get_audit() -> dict[str, Any]:
    """Return audit log and all generated stories for grading."""
    return {
        "calls": _audit_log,
        "generated_stories": _generated_stories,
    }


@app.post("/content-gen/reset")
def reset_state() -> dict[str, str]:
    """Reset service state for a new test run."""
    global _audit_log, _generated_stories
    _audit_log = []
    _generated_stories = []
    _load_fixtures()
    return {"status": "reset"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "9112")))