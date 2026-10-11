#!/usr/bin/env python3
"""HTTP Mock Service for Web - AHR82 disinfo misleading review task.

Provides Google search and webpage fetching capabilities.
"""

import json
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Mock Web API")

FIXTURES_PATH = Path("/opt/mock_service/web/data")

# In-memory state
_search_results: list[dict[str, Any]] = []
_pages: dict[str, dict[str, Any]] = {}
_audit_log: list[dict[str, Any]] = []


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


def _load_fixtures() -> None:
    """Load search results and page fixtures."""
    global _search_results, _pages

    fixtures_path = Path(os.environ.get("WEB_FIXTURES", str(FIXTURES_PATH)))

    # Load search results
    search_path = fixtures_path / "search_results.json"
    if search_path.exists():
        with open(search_path) as f:
            _search_results = json.load(f)
    else:
        print(f"[WEB] Warning: Search results file not found: {search_path}")
        _search_results = []

    # Load pages
    pages_path = fixtures_path / "pages.json"
    if pages_path.exists():
        with open(pages_path) as f:
            pages_list = json.load(f)
            _pages = {p["url"]: p for p in pages_list if "url" in p}
    else:
        print(f"[WEB] Warning: Pages file not found: {pages_path}")
        _pages = {}


_load_fixtures()


def _log_call(endpoint: str, request_body: dict, response_body: Any) -> None:
    _audit_log.append({
        "endpoint": endpoint,
        "request_body": request_body,
        "response_body": response_body,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


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
def web_search(req: SearchRequest) -> dict[str, Any]:
    """Keyword-matched web search. Returns results ranked by keyword overlap."""
    query_tokens = _tokenize(req.query)

    scored: list[tuple[int, int, dict]] = []
    for idx, item in enumerate(_search_results):
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
def fetch_page(req: FetchRequest) -> dict[str, Any]:
    """Fetch a web page by URL. Returns page content from fixtures."""
    page = _pages.get(req.url)

    if page:
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
                "url": page.get("url", req.url),
                "title": page.get("title", ""),
                "content": page.get("content", ""),
                "content_type": page.get("content_type", "text/html"),
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }
    else:
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
    return {"calls": _audit_log}


@app.post("/web/reset")
def reset_state() -> dict[str, str]:
    global _audit_log
    _audit_log = []
    _load_fixtures()
    return {"status": "reset"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "9113")))