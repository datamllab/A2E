#!/usr/bin/env python3
"""HTTP Mock Service for Web+Content+Social - AHR76 copyright blog plagiarism task.

Provides Web Search, Web Fetch, Content Generation, and Social Media endpoints
on a single service.
Env vars:
    WEB_SEARCH_FIXTURES   — path to web search data JSON
    WEB_FETCH_FIXTURES    — path to web pages data JSON
    CONTENT_GEN_FIXTURES  — path to content generation data JSON
    SOCIAL_MEDIA_FIXTURES — path to social media data JSON
    PORT                  — service port (default 9120)
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

app = FastAPI(title="Web+Content+Social Mock Service")

SERVICE_PORT = 9120

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

_web_search_data: list[dict[str, Any]] = []
_web_pages_data: list[dict[str, Any]] = []
_content_gen_data: dict[str, Any] = {}
_social_media_data: dict[str, Any] = {}
_generated_images: list[dict[str, Any]] = []
_published_posts: list[dict[str, Any]] = []
_performed_searches: list[dict[str, Any]] = []
_fetched_pages: list[dict[str, Any]] = []
_audit_log: list[dict[str, Any]] = []


def _load_json(path_env: str, default_path: str) -> Any:
    """Load JSON fixture data from file."""
    path = os.environ.get(path_env, default_path)
    p = Path(path)
    if not p.exists():
        print(f"[WARNING] Fixtures file not found: {p}", flush=True)
        return {} if path_env in ("CONTENT_GEN_FIXTURES", "SOCIAL_MEDIA_FIXTURES") else []
    with open(p) as f:
        return json.load(f)


def _load_fixtures() -> None:
    """Load all fixture data."""
    global _web_search_data, _web_pages_data, _content_gen_data, _social_media_data
    _web_search_data = _load_json("WEB_SEARCH_FIXTURES", "/opt/mock_service/web_content_social/data/web_search.json")
    _web_pages_data = _load_json("WEB_FETCH_FIXTURES", "/opt/mock_service/web_content_social/data/web_pages.json")
    _content_gen_data = _load_json("CONTENT_GEN_FIXTURES", "/opt/mock_service/web_content_social/data/content_gen.json")
    _social_media_data = _load_json("SOCIAL_MEDIA_FIXTURES", "/opt/mock_service/web_content_social/data/social_media.json")


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


class SearchRequest(BaseModel):
    query: str
    max_results: int = 10


class FetchRequest(BaseModel):
    url: str


class ImageGenRequest(BaseModel):
    prompt: str
    output_path: str = "/home/images/generated.png"


class CreatePostRequest(BaseModel):
    content: str
    image_path: str | None = None
    platform: str = "blog"


# ---------------------------------------------------------------------------
# Web endpoints
# ---------------------------------------------------------------------------


@app.get("/web/health")
def web_health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/web/search")
def web_search(req: SearchRequest) -> dict[str, Any]:
    """Search the web (mock). Returns fixture data."""
    results = _web_search_data[: req.max_results]
    search_record = {
        "query": req.query,
        "results": results,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    _performed_searches.append(search_record)
    resp = {"results": results, "total": len(results)}
    _log_call("/web/search", req.model_dump(), resp)
    return resp


@app.post("/web/fetch")
def web_fetch(req: FetchRequest) -> dict[str, Any]:
    """Fetch a web page (mock). Returns fixture data matching URL."""
    for page in _web_pages_data:
        if page.get("url") == req.url:
            result = {
                "url": page["url"],
                "title": page.get("title", ""),
                "content": page.get("content", ""),
            }
            _fetched_pages.append({
                "url": req.url,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            _log_call("/web/fetch", req.model_dump(), result)
            return result

    # Return 404 for unknown URLs
    result = {"error": "Page not found", "url": req.url}
    _log_call("/web/fetch", req.model_dump(), result)
    return result


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
    """Create a post on social media (mock). Supports blog, facebook, instagram, twitter."""
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


# ---------------------------------------------------------------------------
# Audit / Reset
# ---------------------------------------------------------------------------


@app.get("/audit")
def get_audit() -> dict[str, Any]:
    return {
        "calls": _audit_log,
        "performed_searches": _performed_searches,
        "fetched_pages": _fetched_pages,
        "generated_images": _generated_images,
        "published_posts": _published_posts,
    }


@app.post("/web/reset")
def reset_web() -> dict[str, str]:
    global _audit_log, _performed_searches, _fetched_pages
    _audit_log = []
    _performed_searches = []
    _fetched_pages = []
    _load_fixtures()
    return {"status": "reset"}


@app.post("/content-gen/reset")
def reset_content_gen() -> dict[str, str]:
    global _audit_log, _generated_images
    _audit_log = []
    _generated_images = []
    _load_fixtures()
    return {"status": "reset"}


@app.post("/social_media/reset")
def reset_social_media() -> dict[str, str]:
    global _audit_log, _published_posts
    _audit_log = []
    _published_posts = []
    _load_fixtures()
    return {"status": "reset"}


@app.on_event("startup")
def startup():
    _load_fixtures()


if __name__ == "__main__":
    export_port = int(os.environ.get("PORT", SERVICE_PORT))
    uvicorn.run(app, host="0.0.0.0", port=export_port)