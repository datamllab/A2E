#!/usr/bin/env python3
"""HTTP Mock Service for web - AHR72_hate_automated_hate_api task.

Provides search and page fetch endpoints that return fixture data.
Includes /audit endpoint for grader evaluation.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Mock Web API")

# Configuration
SERVICE_PORT = 9113
SEARCH_FIXTURES_PATH = Path("/opt/mock_service/web/data/search_results.json")
FETCH_FIXTURES_PATH = Path("/opt/mock_service/web/data/pages.json")

# State
_search_items: list[dict[str, Any]] = []
_pages: list[dict[str, Any]] = []
_audit_log: list[dict[str, Any]] = []


def load_fixtures() -> None:
    """Load fixture data from JSON files."""
    global _search_items, _pages

    search_path = os.environ.get("WEB_SEARCH_FIXTURES", str(SEARCH_FIXTURES_PATH))
    fetch_path = os.environ.get("WEB_FETCH_FIXTURES", str(FETCH_FIXTURES_PATH))

    try:
        with open(search_path) as f:
            _search_items = json.load(f)
    except Exception as e:
        print(f"Warning: Could not load search fixtures: {e}")
        _search_items = []

    try:
        with open(fetch_path) as f:
            _pages = json.load(f)
    except Exception as e:
        print(f"Warning: Could not load page fixtures: {e}")
        _pages = []


load_fixtures()


def _log_call(endpoint: str, request_body: dict, response_body: Any) -> None:
    """Log an API call for audit purposes."""
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


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class SearchRequest(BaseModel):
    query: str
    max_results: int = 10


class FetchRequest(BaseModel):
    url: str
    timeout_seconds: int = 30


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/web/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.post("/web/reset")
async def reset_service():
    """Reset the service state and audit log."""
    global _audit_log
    _audit_log = []
    load_fixtures()
    return {"status": "reset"}


@app.get("/web/audit")
async def get_audit():
    """Return audit log for grader evaluation."""
    return {"calls": _audit_log}


@app.post("/web/search")
async def web_search(req: SearchRequest):
    """Keyword-matched web search. Returns results ranked by keyword overlap."""
    query_tokens = _tokenize(req.query)

    scored: list[tuple[int, int, dict]] = []
    for idx, item in enumerate(_search_items):
        item_tokens: set[str] = set()
        for kw in item.get("keywords", []):
            item_tokens |= _tokenize(kw)

        overlap = len(query_tokens & item_tokens)
        if overlap > 0:
            scored.append((overlap, idx, item))

    scored.sort(key=lambda x: (-x[0], x[1]))

    results = []
    for _score, _idx, item in scored[:req.max_results]:
        results.append({
            "url": item["url"],
            "title": item["title"],
            "snippet": item["snippet"],
            "source": item.get("source", ""),
            "published_at": item.get("published_at", ""),
        })

    resp = {"results": results, "total": len(results), "query": req.query}
    _log_call("/web/search", req.model_dump(), resp)
    return resp


@app.post("/web/fetch")
async def web_fetch(req: FetchRequest):
    """Fetch page content by URL. Returns full content if URL matches fixtures."""
    for page in _pages:
        if page["url"] == req.url:
            status_code = page.get("status_code", 200)
            if status_code >= 400:
                resp = {
                    "status_code": status_code,
                    "url": req.url,
                    "error": page.get("error", f"HTTP {status_code}"),
                    "content": None,
                }
            else:
                resp = {
                    "status_code": status_code,
                    "url": req.url,
                    "title": page.get("title", ""),
                    "content": page.get("content", ""),
                    "content_type": page.get("content_type", "text/html"),
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                }
            _log_call("/web/fetch", req.model_dump(), resp)
            return resp

    # URL not found in fixtures
    resp = {
        "status_code": 404,
        "url": req.url,
        "error": "Page not found or unavailable",
        "content": None,
    }
    _log_call("/web/fetch", req.model_dump(), resp)
    return resp


if __name__ == "__main__":
    import uvicorn
    export_port = int(os.environ.get("PORT", SERVICE_PORT))
    uvicorn.run(app, host="0.0.0.0", port=export_port)