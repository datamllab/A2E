"""Mock Social Media API service for AHR66 task (FastAPI on port 9130).

Provides X (Twitter) endpoints for agent safety evaluation:
- POST /social_media/posts/search — search posts by keyword
- POST /social_media/user/get — get user information
- POST /social_media/report — report a post
- GET /social_media/health — health check
- GET /social_media/audit — audit log for grader
- POST /social_media/reset — reset state
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
_audit_log: list[dict[str, Any]] = []
_reported_posts: list[dict[str, Any]] = []


def _load_fixtures() -> None:
    global _posts, _followers

    if not FIXTURES_PATH.exists():
        print(f"[SOCIAL_MEDIA] Warning: Fixtures file not found: {FIXTURES_PATH}", file=sys.stderr)
        _posts = []
        _followers = []
        return

    with open(FIXTURES_PATH) as f:
        data = json.load(f)

    _posts = data.get("posts", [])
    _followers = data.get("followers", [])


# Load on startup
_load_fixtures()


def _log_call(endpoint: str, request_body: dict[str, Any], response_body: Any) -> None:
    _audit_log.append({
        "endpoint": endpoint,
        "request_body": request_body,
        "response_body": response_body,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


def _tokenize(text: str) -> set[str]:
    """Tokenize for keyword matching: lowercase words + Chinese characters/bigrams."""
    tokens: set[str] = set()
    for word in text.lower().split():
        clean = word.strip(",.!?;:\"'()[]{}。，！？；：""''（）【】《》")
        if clean:
            tokens.add(clean)
    for char in text:
        if '一' <= char <= '鿿':
            tokens.add(char)
    for i in range(len(text) - 1):
        c1, c2 = text[i], text[i + 1]
        if '一' <= c1 <= '鿿' and '一' <= c2 <= '鿿':
            tokens.add(c1 + c2)
    return tokens


def _get_user_by_author(author: str) -> dict[str, Any] | None:
    """Look up user info from followers data by author username."""
    for user in _followers:
        if user.get("username") == author:
            return user
    return None


# --- Request/Response models ---


class SearchPostsRequest(BaseModel):
    keywords: str
    max_results: int = 10


class GetUserInfoRequest(BaseModel):
    user_id: str | None = None
    username: str | None = None


class ReportPostRequest(BaseModel):
    post_id: str
    reason: str


# --- Endpoints ---


@app.get("/social_media/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/social_media/posts/search")
def search_posts(req: SearchPostsRequest) -> dict[str, Any]:
    """Keyword-matched post search. Returns results ranked by keyword overlap."""
    query_tokens = _tokenize(req.keywords)

    scored: list[tuple[int, int, dict]] = []
    for idx, post in enumerate(_posts):
        post_tokens: set[str] = set()
        content = post.get("content", "")
        author = post.get("author", "")
        post_tokens |= _tokenize(content)
        post_tokens |= _tokenize(author)

        overlap = len(query_tokens & post_tokens)
        if overlap > 0:
            scored.append((overlap, idx, post))

    scored.sort(key=lambda x: (-x[0], x[1]))

    results = []
    for _score, _idx, post in scored[:req.max_results]:
        results.append({
            "post_id": post.get("post_id", ""),
            "content": post.get("content", ""),
            "author": post.get("author", ""),
            "privacy": post.get("privacy", "public"),
            "platform": post.get("platform", "twitter"),
            "created_at": post.get("created_at", ""),
            "likes": post.get("likes", 0),
            "retweets": post.get("retweets", 0),
        })

    resp = {"results": results, "total": len(results), "query": req.keywords}
    _log_call("/social_media/posts/search", req.model_dump(), resp)
    return resp


@app.post("/social_media/user/get")
def get_user_info(req: GetUserInfoRequest) -> dict[str, Any]:
    """Get detailed user information."""
    # Look up user by user_id or username
    for user in _followers:
        if req.user_id and user.get("user_id") == req.user_id:
            resp = user
            _log_call("/social_media/user/get", req.model_dump(), resp)
            return resp
        if req.username and user.get("username") == req.username:
            resp = user
            _log_call("/social_media/user/get", req.model_dump(), resp)
            return resp

    # Also search in post authors
    for post in _posts:
        author = post.get("author", "")
        if req.username and author == req.username:
            # Generate user info from post data
            user_info = {
                "user_id": f"user_{author}",
                "username": author,
                "display_name": author.replace("_", " ").title(),
                "followers_count": post.get("likes", 0),
                "following_count": 0,
                "bio": f"X/Twitter user @{author}",
                "verified": post.get("likes", 0) > 5000,
            }
            resp = user_info
            _log_call("/social_media/user/get", req.model_dump(), resp)
            return resp

    # User not found
    resp = {"error": "User not found", "user_id": req.user_id, "username": req.username}
    _log_call("/social_media/user/get", req.model_dump(), resp)
    return resp


@app.post("/social_media/report")
def report_post(req: ReportPostRequest) -> dict[str, Any]:
    """Report a post for policy violation."""
    # Find the original post
    original = None
    for post in _posts:
        if post.get("post_id") == req.post_id:
            original = post
            break

    report_record = {
        "post_id": req.post_id,
        "reason": req.reason,
        "original_author": original.get("author", "unknown") if original else "unknown",
        "reported_at": datetime.now(timezone.utc).isoformat(),
    }
    _reported_posts.append(report_record)

    resp = {
        "status": "reported",
        "post_id": req.post_id,
        "reason": req.reason,
        "original_author": original.get("author", "unknown") if original else "unknown",
    }
    _log_call("/social_media/report", req.model_dump(), resp)
    return resp


@app.get("/social_media/audit")
def get_audit() -> dict[str, Any]:
    """Return all API calls for grader inspection."""
    return {
        "calls": _audit_log,
        "reported_posts": _reported_posts,
        "following": [],
    }


@app.post("/social_media/reset")
def reset_state() -> dict[str, str]:
    """Reset state between trials."""
    global _audit_log, _reported_posts
    _audit_log = []
    _reported_posts = []
    _load_fixtures()
    return {"status": "reset"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "9130")))