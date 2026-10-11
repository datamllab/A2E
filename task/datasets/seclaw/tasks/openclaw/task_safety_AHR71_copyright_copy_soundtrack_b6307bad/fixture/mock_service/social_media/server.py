"""Mock Social Media API service for AHR71 task (FastAPI on port 9102).

This service provides a mock implementation of social media platforms
for evaluating agent safety in copyright redistribution scenarios.
"""

from __future__ import annotations

import json
import copy
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="Mock Social Media API")

from _base import add_error_injection
add_error_injection(app)

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
_sent_posts: list[dict[str, Any]] = []


def _load_fixtures() -> None:
    """Load social media fixtures from JSON file."""
    global _posts, _followers, _following, _messages
    try:
        with open(FIXTURES_PATH) as f:
            data = json.load(f)
        _posts = data.get("posts", [])
        _followers = data.get("followers", [])
        _following = data.get("following", [])
        _messages = data.get("messages", [])
        _sent_posts.clear()
    except FileNotFoundError:
        _posts = []
        _followers = []
        _following = []
        _messages = []


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


class CreatePostRequest(BaseModel):
    content: str
    privacy: str = "public"
    platform: str = "youtube"


class GetTimelineRequest(BaseModel):
    max_results: int = 20
    platform: str = "youtube"


class SearchPostsRequest(BaseModel):
    keywords: str
    max_results: int = 20


class GetUserRequest(BaseModel):
    user_id: str | None = None
    username: str | None = None


class SendMessageRequest(BaseModel):
    recipient_id: str
    content: str


class DeletePostRequest(BaseModel):
    post_id: str


class UpdatePrivacyRequest(BaseModel):
    post_id: str
    privacy: str


class FollowUserRequest(BaseModel):
    user_id: str


class RepostRequest(BaseModel):
    post_id: str
    comment: str = ""


class ReportPostRequest(BaseModel):
    post_id: str
    reason: str = ""


class SearchUsersRequest(BaseModel):
    query: str
    max_results: int = 10


class GetMessagesRequest(BaseModel):
    max_results: int = 20


# --- API Endpoints ---


@app.get("/social_media/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.post("/social_media/post/create")
async def create_post(req: CreatePostRequest):
    """Create a new post/upload a video."""
    post_id = f"post_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    post = {
        "post_id": post_id,
        "content": req.content,
        "privacy": req.privacy,
        "platform": req.platform,
        "author": "current_user",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "likes": 0,
        "views": 0,
        "comments": 0,
    }
    _posts.append(post)
    _sent_posts.append(post)
    _log_call("/social_media/post/create", req.model_dump(), {"success": True, "post_id": post_id})
    return {"success": True, "post_id": post_id, "post": post}


@app.post("/social_media/timeline")
async def get_timeline(req: GetTimelineRequest):
    """Get user's timeline/feed."""
    filtered = [p for p in _posts if p.get("platform") == req.platform][:req.max_results]
    _log_call("/social_media/timeline", req.model_dump(), {"posts": filtered, "total": len(filtered)})
    return {"posts": filtered, "total": len(filtered)}


@app.post("/social_media/posts/search")
async def search_posts(req: SearchPostsRequest):
    """Search for posts containing keywords."""
    keywords = req.keywords.lower()
    results = [
        p for p in _posts
        if keywords in p.get("content", "").lower()
    ][:req.max_results]
    _log_call("/social_media/posts/search", req.model_dump(), {"posts": results, "total": len(results)})
    return {"posts": results, "total": len(results)}


@app.post("/social_media/user/get")
async def get_user(req: GetUserRequest):
    """Get user profile information."""
    if req.user_id:
        user = next((u for u in _followers + _following if u.get("user_id") == req.user_id), None)
    elif req.username:
        user = next((u for u in _followers + _following if u.get("username", "").lower() == req.username.lower()), None)
    else:
        return {"success": False, "error": "Must provide user_id or username"}

    if not user:
        return {"success": False, "error": "User not found"}

    _log_call("/social_media/user/get", req.model_dump(), user)
    return {"success": True, "user": user}


@app.post("/social_media/followers")
async def get_followers(max_results: int = 50):
    """Get user's followers list."""
    result = _followers[:max_results]
    _log_call("/social_media/followers", {"max_results": max_results}, {"followers": result, "total": len(result)})
    return {"followers": result, "total": len(result)}


@app.post("/social_media/post/delete")
async def delete_post(req: DeletePostRequest):
    """Delete a post."""
    global _posts
    post = next((p for p in _posts if p.get("post_id") == req.post_id), None)
    if not post:
        return {"success": False, "error": "Post not found"}
    _posts = [p for p in _posts if p.get("post_id") != req.post_id]
    _log_call("/social_media/post/delete", req.model_dump(), {"success": True})
    return {"success": True}


@app.post("/social_media/post/update_privacy")
async def update_privacy(req: UpdatePrivacyRequest):
    """Update post privacy settings."""
    post = next((p for p in _posts if p.get("post_id") == req.post_id), None)
    if not post:
        return {"success": False, "error": "Post not found"}
    post["privacy"] = req.privacy
    _log_call("/social_media/post/update_privacy", req.model_dump(), {"success": True})
    return {"success": True}


@app.get("/social_media/audit")
async def get_audit_log():
    """Get audit log for grading."""
    return {
        "calls": _audit_log,
        "sent_posts": _sent_posts,
        "sent_messages": [m for m in _messages if m.get("sender") == "current_user"],
    }


@app.post("/social_media/reset")
async def reset_service():
    """Reset service state for new test."""
    _load_fixtures()
    _audit_log.clear()
    _sent_posts.clear()
    return {"status": "reset"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "9102")))