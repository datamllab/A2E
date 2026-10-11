"""Mock Social Media API service for AHR96 task (FastAPI on port 9130).

Provides Instagram post search endpoint for agent safety evaluation.
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

app = FastAPI(title="Mock Social Media API")

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
    "SOCIAL_MEDIA_FIXTURES",
    str(Path(__file__).resolve().parent / "data" / "social_media.json"),
))

# In-memory state
_posts: list[dict[str, Any]] = []
_followers: list[dict[str, Any]] = []
_following: list[dict[str, Any]] = []
_messages: list[dict[str, Any]] = []
_audit_log: list[dict[str, Any]] = []


def _load_fixtures() -> None:
    """Load social media fixtures from JSON file."""
    global _posts, _followers, _following, _messages

    if not FIXTURES_PATH.exists():
        print(f"[SOCIAL_MEDIA] Warning: Fixtures file not found: {FIXTURES_PATH}", file=sys.stderr)
        _posts, _followers, _following, _messages = [], [], [], []
        return

    with open(FIXTURES_PATH) as f:
        data = json.load(f)
    _posts = data.get("posts", [])
    _followers = data.get("followers", [])
    _following = data.get("following", [])
    _messages = data.get("messages", [])


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


class SearchPostsRequest(BaseModel):
    query: str
    max_results: int = 10


# --- Endpoints ---


@app.get("/social_media/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.post("/social_media/posts/search")
async def search_posts(req: SearchPostsRequest):
    """Search for Instagram posts matching keywords or by user."""
    query_lower = req.query.lower()
    results = []

    for post in _posts:
        content_lower = post.get("content", "").lower()
        author_lower = post.get("author", "").lower()
        if query_lower in content_lower or query_lower in author_lower:
            results.append(post)

    resp = {
        "success": True,
        "posts": results[:req.max_results],
        "count": len(results[:req.max_results]),
    }
    _log_call("/social_media/posts/search", req.model_dump(), resp)
    return resp


@app.get("/social_media/audit")
async def get_audit_log():
    """Get audit log for grading."""
    return {"calls": _audit_log}


@app.post("/social_media/reset")
async def reset_service():
    """Reset service state for new test."""
    _load_fixtures()
    _audit_log.clear()
    return {"status": "reset"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "9130")))