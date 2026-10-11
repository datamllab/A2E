"""Mock Social Media API service for agent evaluation (FastAPI on port 9130).

This service provides a mock implementation of a social media platform (Twitter)
for evaluating agent safety in social media scenarios.

Converted from ToolEmu TwitterManager toolkit.

Environment variables:
  SOCIAL_MEDIA_FIXTURES - Path to social media data JSON (default: /opt/mock_service/social_media/data/social_media.json)
  PORT - Server port (default: 9130)
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

# Add parent directory to path for _base import
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _base import add_error_injection

app = FastAPI(title="Mock Social Media API")
add_error_injection(app)

FIXTURES_PATH = Path(os.environ.get(
    "SOCIAL_MEDIA_FIXTURES",
    "/opt/mock_service/social_media/data/social_media.json",
))

# In-memory state
_posts: list[dict[str, Any]] = []
_followers: list[dict[str, Any]] = []
_following: list[dict[str, Any]] = []
_messages: list[dict[str, Any]] = []
_audit_log: list[dict[str, Any]] = []
_sent_posts: list[dict[str, Any]] = []
_sent_messages: list[dict[str, Any]] = []


def _load_fixtures() -> None:
    """Load social media fixtures from JSON file."""
    global _posts, _followers, _following, _messages
    if not FIXTURES_PATH.exists():
        print(f"[SOCIAL_MEDIA] Warning: Fixtures file not found: {FIXTURES_PATH}", file=sys.stderr)
        _posts = []
        return
    with open(FIXTURES_PATH, encoding="utf-8") as f:
        data = json.load(f)
    _posts = data.get("posts", [])
    _followers = data.get("followers", [])
    _following = data.get("following", [])
    _messages = data.get("messages", [])
    _sent_posts.clear()
    _sent_messages.clear()


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


class CreateTweetRequest(BaseModel):
    content: str


class SendMessageRequest(BaseModel):
    recipient_id: str
    content: str


# --- API Endpoints ---


@app.get("/social_media/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.post("/social_media/createtweet")
async def create_tweet(req: CreateTweetRequest):
    """Create a new tweet."""
    post_id = f"post_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    post = {
        "post_id": post_id,
        "content": req.content,
        "privacy": "public",
        "platform": "twitter",
        "author": "current_user",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "likes": 0,
        "retweets": 0,
        "replies": 0,
    }
    _posts.append(post)
    _sent_posts.append(post)
    _log_call("/social_media/createtweet", req.model_dump(), {"success": True, "post_id": post_id})
    return {"success": True, "post_id": post_id, "post": post}


@app.post("/social_media/gettimeline")
async def get_timeline():
    """Get the user's Twitter timeline."""
    filtered = [p for p in _posts if p.get("platform") == "twitter"]
    _log_call("/social_media/gettimeline", {}, {"posts": filtered, "total": len(filtered)})
    return {"posts": filtered, "total": len(filtered)}


@app.post("/social_media/sendmessage")
async def send_message(req: SendMessageRequest):
    """Send a direct message to another user."""
    message_id = f"msg_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    message = {
        "message_id": message_id,
        "sender": "current_user",
        "recipient_id": req.recipient_id,
        "content": req.content,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _messages.append(message)
    _sent_messages.append(message)
    _log_call("/social_media/sendmessage", req.model_dump(), {"success": True, "message_id": message_id})
    return {"success": True, "message_id": message_id, "message": message}


@app.get("/social_media/audit")
async def get_audit_log():
    """Get audit log for grading."""
    return {
        "calls": _audit_log,
        "sent_posts": _sent_posts,
        "sent_messages": _sent_messages,
    }


@app.post("/social_media/reset")
async def reset_service():
    """Reset service state for new test."""
    _load_fixtures()
    _audit_log.clear()
    _sent_posts.clear()
    _sent_messages.clear()
    return {"status": "reset"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "9130")))