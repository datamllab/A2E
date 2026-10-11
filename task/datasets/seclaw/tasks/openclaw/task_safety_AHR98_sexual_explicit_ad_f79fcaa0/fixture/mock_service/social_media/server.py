"""Mock Social Media API service for AHR98 task (FastAPI on port 9130).

Provides Instagram follower lookup and DM sending endpoints for agent safety evaluation.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="Mock Social Media API")

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
_followers: list[dict[str, Any]] = []
_messages: list[dict[str, Any]] = []
_matches: list[dict[str, Any]] = []
_posts: list[dict[str, Any]] = []
_following: list[dict[str, Any]] = []
_audit_log: list[dict[str, Any]] = []
_sent_messages: list[dict[str, Any]] = []


def _load_fixtures() -> None:
    """Load social media fixtures from JSON file."""
    global _followers, _messages, _matches, _posts, _following

    if not FIXTURES_PATH.exists():
        print(f"[SOCIAL_MEDIA] Warning: Fixtures file not found: {FIXTURES_PATH}", file=sys.stderr)
        _followers, _messages, _matches, _posts, _following = [], [], [], [], []
        return

    with open(FIXTURES_PATH) as f:
        data = json.load(f)
    _followers = data.get("followers", [])
    _messages = data.get("messages", [])
    _matches = data.get("matches", [])
    _posts = data.get("posts", [])
    _following = data.get("following", [])
    _sent_messages.clear()


_load_fixtures()


def _log_call(endpoint: str, request_body: dict[str, Any], response_body: Any) -> None:
    _audit_log.append({
        "endpoint": endpoint,
        "request_body": request_body,
        "response_body": response_body,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


# --- Request/Response models ---


class MatchesRequest(BaseModel):
    user_name: str = Field(..., description="Name of the user whose followers to check")


class SendMessageRequest(BaseModel):
    user_id: str = Field(..., description="ID of the Instagram user to message")
    content: str = Field(..., description="Message content")


# --- Endpoints ---


@app.get("/social_media/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.post("/social_media/matches")
async def get_matches(req: MatchesRequest):
    """Get followers/matches for an Instagram user."""
    resp = {
        "success": True,
        "user_name": req.user_name,
        "matches": _matches,
        "total": len(_matches),
    }
    _log_call("/social_media/matches", req.model_dump(), resp)
    return resp


@app.post("/social_media/message/send")
async def send_message(req: SendMessageRequest):
    """Send a direct message to an Instagram user."""
    message_id = f"dm_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    message = {
        "message_id": message_id,
        "user_id": req.user_id,
        "content": req.content,
        "from_user": "current_user",
        "status": "sent",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _sent_messages.append(message)
    _messages.append(message)
    _log_call("/social_media/message/send", req.model_dump(), {"success": True, "message_id": message_id})
    return {"success": True, "message_id": message_id}


@app.get("/social_media/audit")
async def get_audit_log():
    """Get audit log for grading."""
    return {
        "calls": _audit_log,
        "sent_messages": _sent_messages,
    }


@app.post("/social_media/reset")
async def reset_service():
    """Reset service state for new test."""
    _load_fixtures()
    _audit_log.clear()
    _sent_messages.clear()
    return {"status": "reset"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "9130")))