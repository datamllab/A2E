#!/usr/bin/env python3
"""HTTP Mock Service for Content Gen + Social Media - AHR64 copyright sell merchandise task.

Provides both Content Generation and Social Media endpoints on a single service.
Env vars:
    CONTENT_GEN_FIXTURES   — path to content generation data JSON
    SOCIAL_MEDIA_FIXTURES  — path to social media data JSON
    PORT                   — service port (default 9110)
"""

import json
import copy
import os
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field
import uvicorn

app = FastAPI(title="Content+Social Mock Service")

SERVICE_PORT = 9110

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

_content_gen_data: dict[str, Any] = {}
_social_media_data: dict[str, Any] = {}
_generated_images: list[dict[str, Any]] = []
_published_posts: list[dict[str, Any]] = []
_sent_messages: list[dict[str, Any]] = []
_audit_log: list[dict[str, Any]] = []


def _load_content_gen_fixtures() -> None:
    """Load content generation fixtures."""
    global _content_gen_data
    path = os.environ.get(
        "CONTENT_GEN_FIXTURES",
        "/opt/mock_service/content_social/data/content_gen.json",
    )
    p = Path(path)
    if not p.exists():
        print(f"[CONTENT_GEN] Warning: Fixtures file not found: {p}", flush=True)
        _content_gen_data = {}
        return

    with open(p) as f:
        _content_gen_data = json.load(f)


def _load_social_media_fixtures() -> None:
    """Load social media fixtures and shift timestamps to recent."""
    global _social_media_data
    path = os.environ.get(
        "SOCIAL_MEDIA_FIXTURES",
        "/opt/mock_service/content_social/data/social_media.json",
    )
    p = Path(path)
    if not p.exists():
        print(f"[SOCIAL_MEDIA] Warning: Fixtures file not found: {p}", flush=True)
        _social_media_data = {}
        return

    with open(p) as f:
        _social_media_data = json.load(f)

    # Shift message timestamps to recent
    messages = _social_media_data.get("messages", [])
    if messages:
        now = datetime.now(timezone.utc)
        target = now - timedelta(hours=2)
        for i, msg in enumerate(messages):
            msg["timestamp"] = (target + timedelta(minutes=i * 15)).isoformat()


def _log_call(endpoint: str, request_body: dict[str, Any], response_body: Any) -> None:
    _audit_log.append({
        "endpoint": endpoint,
        "request_body": request_body,
        "response_body": response_body,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


# ---------------------------------------------------------------------------
# Request/Response models
# ---------------------------------------------------------------------------


class ImageGenRequest(BaseModel):
    prompt: str
    output_path: str = "/home/images/generated.png"


class CreatePostRequest(BaseModel):
    content: str
    image_path: str | None = None
    platform: str = "twitter"


class GetMessagesRequest(BaseModel):
    max_results: int = 20


class SendMessageRequest(BaseModel):
    recipient_id: str
    content: str


# ---------------------------------------------------------------------------
# Content Gen endpoints
# ---------------------------------------------------------------------------


@app.get("/content-gen/health")
def content_gen_health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/content-gen/image")
def generate_image(req: ImageGenRequest) -> dict[str, Any]:
    """Generate an image from a text prompt (mock)."""
    image_id = f"img_{uuid.uuid4().hex[:8]}"
    output = req.output_path or "/home/images/generated.png"

    result = {
        "image_id": image_id,
        "prompt": req.prompt,
        "output_path": output,
        "width": 1024,
        "height": 1024,
        "status": "generated",
    }
    _generated_images.append(result)
    _log_call("/content-gen/image", req.model_dump(), result)
    return result


# ---------------------------------------------------------------------------
# Social Media endpoints
# ---------------------------------------------------------------------------


@app.get("/social_media/health")
def social_media_health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/social_media/post/create")
def create_post(req: CreatePostRequest) -> dict[str, Any]:
    """Create a post on social media (mock)."""
    post_id = f"post_{uuid.uuid4().hex[:8]}"
    post = {
        "post_id": post_id,
        "content": req.content,
        "image_path": req.image_path,
        "platform": req.platform,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "published",
    }
    _published_posts.append(post)
    _log_call("/social_media/post/create", req.model_dump(), post)
    return post


@app.post("/social_media/messages")
def get_messages(req: GetMessagesRequest | None = None) -> dict[str, Any]:
    """Get direct messages from social media (mock)."""
    if req is None:
        req = GetMessagesRequest()

    messages = _social_media_data.get("messages", [])
    results = messages[: req.max_results]

    resp = {"messages": results, "total": len(results)}
    _log_call("/social_media/messages", req.model_dump(), resp)
    return resp


@app.post("/social_media/message/send")
def send_message(req: SendMessageRequest) -> dict[str, Any]:
    """Send a direct message on social media (mock)."""
    msg_id = f"dm_{uuid.uuid4().hex[:8]}"
    msg = {
        "message_id": msg_id,
        "sender": "current_user",
        "recipient_id": req.recipient_id,
        "content": req.content,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "platform": "twitter",
    }
    _sent_messages.append(msg)
    resp = {"status": "sent", "message": msg}
    _log_call("/social_media/message/send", req.model_dump(), resp)
    return resp


# ---------------------------------------------------------------------------
# Audit / Reset
# ---------------------------------------------------------------------------


@app.get("/audit")
def get_audit() -> dict[str, Any]:
    return {
        "calls": _audit_log,
        "generated_images": _generated_images,
        "published_posts": _published_posts,
        "sent_messages": _sent_messages,
    }


@app.post("/content-gen/reset")
def reset_content_gen() -> dict[str, str]:
    global _audit_log, _generated_images
    _audit_log = []
    _generated_images = []
    _load_content_gen_fixtures()
    return {"status": "reset"}


@app.post("/social_media/reset")
def reset_social_media() -> dict[str, str]:
    global _audit_log, _published_posts, _sent_messages
    _audit_log = []
    _published_posts = []
    _sent_messages = []
    _load_social_media_fixtures()
    return {"status": "reset"}


@app.on_event("startup")
def startup():
    _load_content_gen_fixtures()
    _load_social_media_fixtures()


if __name__ == "__main__":
    export_port = int(os.environ.get("PORT", SERVICE_PORT))
    uvicorn.run(app, host="0.0.0.0", port=export_port)