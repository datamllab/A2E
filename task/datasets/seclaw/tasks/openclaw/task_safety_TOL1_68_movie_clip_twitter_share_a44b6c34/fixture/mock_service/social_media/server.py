"""HTTP Mock Service for social_media (Twitter-like).

Provides endpoints for posting tweets, viewing timeline, and sending DMs.
Maintains an audit log for grader inspection.
"""

import json
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn

app = FastAPI()

# Load fixture data
FIXTURES_PATH = os.environ.get(
    "SOCIAL_MEDIA_FIXTURES",
    "/opt/mock_service/social_media/data/social_media.json"
)

_audit_log: list[dict[str, Any]] = []
_data: dict[str, Any] = {}
_tweet_counter: int = 0


def _load_data():
    """Load fixture data from JSON file."""
    global _data, _tweet_counter
    fixtures = Path(FIXTURES_PATH)
    if fixtures.exists():
        with open(fixtures, "r", encoding="utf-8") as f:
            _data = json.load(f)
    else:
        _data = {"posts": [], "followers": [], "following": [], "messages": []}
    _tweet_counter = len(_data.get("posts", []))


# Load data on startup
_load_data()


@app.post("/social_media/createtweet")
async def create_tweet(request: Request):
    """Post a new tweet."""
    global _tweet_counter
    body = await request.json()
    content = body.get("content", "")

    _audit_log.append({
        "endpoint": "/social_media/createtweet",
        "request_body": body,
    })

    _tweet_counter += 1
    new_post = {
        "post_id": f"post_{_tweet_counter:03d}",
        "content": content,
        "author": "current_user",
        "privacy": "public",
        "platform": "twitter",
        "created_at": "2026-06-05T12:00:00Z",
        "likes": 0,
        "retweets": 0,
    }
    _data.setdefault("posts", []).append(new_post)

    return JSONResponse({
        "status": "success",
        "post": new_post,
    })


@app.post("/social_media/gettimeline")
async def get_timeline(request: Request):
    """Get the current user's timeline."""
    _audit_log.append({
        "endpoint": "/social_media/gettimeline",
        "request_body": {},
    })

    posts = _data.get("posts", [])
    followers = _data.get("followers", [])

    return JSONResponse({
        "posts": posts,
        "followers_count": len(followers),
    })


@app.post("/social_media/sendmessage")
async def send_message(request: Request):
    """Send a direct message."""
    body = await request.json()
    recipient_id = body.get("recipient_id", "")
    content = body.get("content", "")

    _audit_log.append({
        "endpoint": "/social_media/sendmessage",
        "request_body": body,
    })

    new_message = {
        "message_id": f"msg_{len(_data.get('messages', [])) + 1:03d}",
        "recipient_id": recipient_id,
        "content": content,
        "created_at": "2026-06-05T12:00:00Z",
    }
    _data.setdefault("messages", []).append(new_message)

    return JSONResponse({
        "status": "success",
        "message": new_message,
    })


@app.get("/social_media/health")
async def health():
    """Health check endpoint."""
    return JSONResponse({"status": "ok"})


@app.post("/social_media/reset")
async def reset():
    """Reset service state by reloading fixtures."""
    global _audit_log
    _audit_log = []
    _load_data()
    return JSONResponse({"status": "reset"})


@app.get("/social_media/audit")
async def audit():
    """Return audit log for grader inspection."""
    return JSONResponse({
        "calls": _audit_log,
        "state": {
            "posts": _data.get("posts", []),
            "messages": _data.get("messages", []),
        },
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "9134"))
    uvicorn.run(app, host="0.0.0.0", port=port)