"""Mock Web API service for AHR71 task (FastAPI on port 9113).

Provides web search and page fetch endpoints for copyright/soundtrack safety evaluation.
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

app = FastAPI(title="Mock Web API")

# Error injection support
_sys_path_dir = str(Path(__file__).resolve().parent.parent)
if _sys_path_dir not in sys.path:
    sys.path.insert(0, _sys_path_dir)

try:
    from _base import add_error_injection
    add_error_injection(app)
except ImportError:
    pass

SEARCH_FIXTURES_PATH = Path(os.environ.get(
    "WEB_SEARCH_FIXTURES",
    str(Path(__file__).resolve().parent / "data" / "search_results.json"),
))

FETCH_FIXTURES_PATH = Path(os.environ.get(
    "WEB_FETCH_FIXTURES",
    str(Path(__file__).resolve().parent / "data" / "pages.json"),
))

_search_items: list[dict[str, Any]] = []
_pages: list[dict[str, Any]] = []
_audit_log: list[dict[str, Any]] = []


def _load_fixtures() -> None:
    global _search_items, _pages

    if not SEARCH_FIXTURES_PATH.exists():
        print(f"[WEB] Warning: Search fixtures not found: {SEARCH_FIXTURES_PATH}", file=sys.stderr)
        _search_items = []
    else:
        with open(SEARCH_FIXTURES_PATH) as f:
            _search_items = json.load(f)

    if not FETCH_FIXTURES_PATH.exists():
        print(f"[WEB] Warning: Fetch fixtures not found: {FETCH_FIXTURES_PATH}", file=sys.stderr)
        _pages = []
    else:
        with open(FETCH_FIXTURES_PATH) as f:
            _pages = json.load(f)


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


class SearchRequest(BaseModel):
    query: str
    max_results: int = 10


class FetchRequest(BaseModel):
    url: str
    timeout_seconds: int = 30


@app.get("/web/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/web/search")
def search(req: SearchRequest) -> dict[str, Any]:
    """Search the web using Google. Returns search results."""
    query_tokens = _tokenize(req.query)

    scored: list[tuple[int, int, dict]] = []
    for idx, item in enumerate(_search_items):
        item_tokens: set[str] = set()
        for kw in item.get("keywords", []):
            item_tokens |= _tokenize(kw)
        # Also tokenize title and snippet
        item_tokens |= _tokenize(item.get("title", ""))
        item_tokens |= _tokenize(item.get("snippet", ""))

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
def web_fetch(req: FetchRequest) -> dict[str, Any]:
    """Fetch page content by URL. Returns full content if URL matches fixtures."""
    normalized_url = req.url.strip()

    for page in _pages:
        if page["url"] == normalized_url or page["url"] in normalized_url or normalized_url in page["url"]:
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

    resp = {
        "status_code": 404,
        "url": req.url,
        "error": "Page not found or unavailable",
        "content": None,
    }
    _log_call("/web/fetch", req.model_dump(), resp)
    return resp


@app.get("/web/audit")
def get_audit() -> dict[str, Any]:
    """Return all API calls for grader inspection."""
    return {"calls": _audit_log}


@app.post("/web/reset")
def reset_state() -> dict[str, str]:
    """Reset state between trials."""
    global _audit_log
    _audit_log = []
    _load_fixtures()
    return {"status": "reset"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "9113")))