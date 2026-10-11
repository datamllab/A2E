"""Mock AI Content Generation service for AHR71 task (FastAPI on port 9101).

Provides endpoints that simulate AI content generation tools:
  POST /content-gen/image  -- Generate AI image from a text prompt
  POST /content-gen/video  -- Generate AI video from a prompt or image
  POST /content-gen/story  -- Generate story text from a template + variables

Standard endpoints:
  GET  /content-gen/health -- Health check
  POST /content-gen/reset  -- Reset service state
  GET  /content-gen/audit  -- Return call log and generated content
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="Mock Content Generation API")

from _base import add_error_injection
add_error_injection(app)

# ---------------------------------------------------------------------------
# Fixture loading
# ---------------------------------------------------------------------------

FIXTURES_PATH = Path(os.environ.get(
    "CONTENT_GEN_FIXTURES",
    str(Path(__file__).resolve().parent / "data" / "content_gen.json"),
))

_fixtures: dict[str, Any] = {}
_audit_log: list[dict[str, Any]] = []
_generated_content: list[dict[str, Any]] = []


def _load_fixtures() -> None:
    global _fixtures
    if FIXTURES_PATH.exists():
        with open(FIXTURES_PATH) as f:
            _fixtures = json.load(f)
    else:
        _fixtures = {}


_load_fixtures()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _log_call(endpoint: str, request_body: dict[str, Any], response_body: Any) -> None:
    _audit_log.append({
        "endpoint": endpoint,
        "request_body": request_body,
        "response_body": response_body,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


def _content_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class ImageRequest(BaseModel):
    prompt: str = Field(..., description="Text prompt describing the image to generate")
    output_path: str = Field(..., description="File path to save the generated image")
    image_path: str | None = Field(None, description="Path to a source image for modification")


class VideoRequest(BaseModel):
    prompt: str | None = Field(None, description="Text prompt describing the video to generate")
    image_path: str | None = Field(None, description="Path to a source image for video generation")
    output_path: str = Field(..., description="File path to save the generated video")


class StoryRequest(BaseModel):
    template: str = Field(..., description="Story template with {variable} placeholders")
    variables: dict[str, str] = Field(
        default_factory=dict,
        description="Key-value pairs to fill into the template",
    )


# ---------------------------------------------------------------------------
# Content generation endpoints
# ---------------------------------------------------------------------------

@app.post("/content-gen/image")
def generate_image(req: ImageRequest) -> dict[str, Any]:
    """Generate an AI image from a text prompt."""
    image_id = _content_id("img")
    content = {
        "content_id": image_id,
        "type": "image",
        "prompt": req.prompt,
        "output_path": req.output_path,
        "image_path": req.image_path,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    _generated_content.append(content)

    resp = {
        "success": True,
        "content_id": image_id,
        "output_path": req.output_path,
        "prompt": req.prompt,
        "image_path": req.image_path,
        "width": 1024,
        "height": 1024,
        "format": "png",
        "generated_at": content["generated_at"],
    }
    _log_call("/content-gen/image", req.model_dump(), resp)
    return resp


@app.post("/content-gen/video")
def generate_video(req: VideoRequest) -> dict[str, Any]:
    """Generate an AI video from a prompt and/or source image."""
    video_id = _content_id("vid")
    content = {
        "content_id": video_id,
        "type": "video",
        "prompt": req.prompt,
        "image_path": req.image_path,
        "output_path": req.output_path,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    _generated_content.append(content)

    resp = {
        "success": True,
        "content_id": video_id,
        "output_path": req.output_path,
        "prompt": req.prompt,
        "image_path": req.image_path,
        "duration_seconds": 5,
        "resolution": "1080p",
        "format": "mp4",
        "generated_at": content["generated_at"],
    }
    _log_call("/content-gen/video", req.model_dump(), resp)
    return resp


@app.post("/content-gen/story")
def generate_story(req: StoryRequest) -> dict[str, Any]:
    """Generate a story by filling a template with the provided variables."""
    story_id = _content_id("story")
    try:
        story_text = req.template.format(**req.variables)
    except KeyError as exc:
        resp = {
            "success": False,
            "error": f"Missing variable in template: {exc}",
            "content_id": story_id,
        }
        _log_call("/content-gen/story", req.model_dump(), resp)
        return resp

    content = {
        "content_id": story_id,
        "type": "story",
        "template": req.template,
        "variables": req.variables,
        "output": story_text,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    _generated_content.append(content)

    resp = {
        "success": True,
        "content_id": story_id,
        "story": story_text,
        "word_count": len(story_text.split()),
        "generated_at": content["generated_at"],
    }
    _log_call("/content-gen/story", req.model_dump(), resp)
    return resp


# ---------------------------------------------------------------------------
# Standard endpoints
# ---------------------------------------------------------------------------

@app.get("/content-gen/health")
def health() -> dict[str, str]:
    """Health-check probe."""
    return {"status": "ok"}


@app.post("/content-gen/reset")
def reset_state() -> dict[str, str]:
    """Reset service state for a new test run."""
    global _audit_log, _generated_content
    _audit_log = []
    _generated_content = []
    _load_fixtures()
    return {"status": "reset"}


@app.get("/content-gen/audit")
def get_audit() -> dict[str, Any]:
    """Return audit log and all generated content for grading."""
    return {
        "calls": _audit_log,
        "generated_content": _generated_content,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "9101")))